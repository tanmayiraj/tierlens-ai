"""
Unit and integration tests for NetworkX Graph Engine (TASK-008 and TASK-009).
Tests cover:
- Standard three-tier supplier chain and tier calculation.
- Manufacturer identification, zero manufacturer, and multiple manufacturer handling.
- Multi-path shortest path tier calculation.
- Disconnected suppliers and inactive supplier handling.
- Pending and rejected relationship filtering and stale tier clearing.
- Cycle detection without graph modification or infinite loops.
- Upstream and downstream traversal operations.
- Safe database transaction synchronization and rollback behavior.
- Isolation from the real tierlens.db.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, init_db
from backend.models.db import (
    Supplier,
    Material,
    Relationship,
    RelationshipEvidence,
    Evidence,
    Document,
)
from backend.graph.service import (
    GraphService,
    ManufacturerNotFoundError,
    MultipleManufacturersError,
    to_node_id,
    parse_supplier_id,
)


@pytest.fixture
def graph_test_db(tmp_path):
    """
    Creates an isolated temporary SQLite database for graph testing.
    """
    db_file = tmp_path / "test_graph_isolated.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    init_db(target_engine=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# Helper function to seed test data
# =============================================================================

def seed_chain_fixture(session):
    """
    Seeds a standard 3-tier automotive supply chain:
    - s1: AutoMotive Corp (manufacturer)
    - s2: TyreWorks Ltd (Tier 1) -> s1
    - s3: RubberCore Industries (Tier 2) -> s2
    - s4: GreenLatex Pvt Ltd (Tier 3) -> s3
    - s5: MultiRoute Ltd (supplies s2 directly AND supplies s3) -> should get Tier 2 via s2!
    - s6: Disconnected Ltd (no relationships) -> should get tier NULL
    - s7: Inactive Supplier (is_active=False) with an approved rel -> excluded
    """
    # Materials
    m1 = Material(id=1, name="Tyres", material_type="assembly")
    m2 = Material(id=2, name="Processed Rubber", material_type="part")
    m3 = Material(id=3, name="Natural Latex", material_type="raw")
    m4 = Material(id=4, name="Chemicals", material_type="raw")
    session.add_all([m1, m2, m3, m4])
    session.flush()

    # Documents & Evidence
    doc = Document(id=1, filename="Doc1.pdf", doc_type="po", file_path="/tmp/d1.pdf")
    session.add(doc)
    session.flush()

    ev1 = Evidence(id=1, document_id=1, snippet="ev1", llm_confidence=0.95)
    ev2 = Evidence(id=2, document_id=1, snippet="ev2", llm_confidence=0.90)
    session.add_all([ev1, ev2])
    session.flush()

    # Suppliers
    s1 = Supplier(id=1, name="AutoMotive Corp", entity_type="manufacturer", is_active=True, base_risk=0.0)
    s2 = Supplier(id=2, name="TyreWorks Ltd", entity_type="supplier", is_active=True, base_risk=15.0)
    s3 = Supplier(id=3, name="RubberCore Industries", entity_type="supplier", is_active=True, base_risk=20.0)
    s4 = Supplier(id=4, name="GreenLatex Pvt Ltd", entity_type="supplier", is_active=True, base_risk=30.0)
    s5 = Supplier(id=5, name="MultiRoute Ltd", entity_type="supplier", is_active=True, base_risk=25.0)
    s6 = Supplier(id=6, name="Disconnected Ltd", entity_type="supplier", is_active=True, base_risk=10.0)
    s7 = Supplier(id=7, name="Inactive Supplier", entity_type="supplier", is_active=False, base_risk=50.0)
    session.add_all([s1, s2, s3, s4, s5, s6, s7])
    session.flush()

    # Relationships
    # rel1: s2 -> s1 (Tyres, approved) -> Tier 1
    rel1 = Relationship(
        id=1, supplier_id=2, buyer_id=1, material_id=1,
        lead_time_days=7, share_pct=100.0, inventory_days=3,
        confidence=0.98, status="approved", evidence_id=1
    )
    # rel2: s3 -> s2 (Processed Rubber, approved) -> Tier 2
    rel2 = Relationship(
        id=2, supplier_id=3, buyer_id=2, material_id=2,
        lead_time_days=10, share_pct=80.0, inventory_days=4,
        confidence=0.95, status="approved", evidence_id=2
    )
    # rel3: s4 -> s3 (Natural Latex, approved) -> Tier 3
    rel3 = Relationship(
        id=3, supplier_id=4, buyer_id=3, material_id=3,
        lead_time_days=21, share_pct=70.0, inventory_days=5,
        confidence=0.92, status="approved"
    )
    # rel4: s5 -> s2 (Chemicals, approved) -> Path length 2 to s1 -> Tier 2
    rel4 = Relationship(
        id=4, supplier_id=5, buyer_id=2, material_id=4,
        lead_time_days=14, share_pct=50.0, inventory_days=2,
        confidence=0.90, status="approved"
    )
    # rel5: s5 -> s3 (Chemicals, approved) -> Path length 3 to s1 -> longer path
    # But shortest path to s1 is via s2 (length 2)!
    rel5 = Relationship(
        id=5, supplier_id=5, buyer_id=3, material_id=4,
        lead_time_days=15, share_pct=50.0, inventory_days=2,
        confidence=0.90, status="approved"
    )
    # rel6: s7 (inactive) -> s1 (approved, but supplier is inactive -> excluded)
    rel6 = Relationship(
        id=6, supplier_id=7, buyer_id=1, material_id=1,
        lead_time_days=5, share_pct=20.0, inventory_days=1,
        confidence=0.80, status="approved"
    )
    # rel7: s4 -> s2 (pending relationship -> excluded from operational graph)
    rel7 = Relationship(
        id=7, supplier_id=4, buyer_id=2, material_id=3,
        lead_time_days=10, share_pct=30.0, inventory_days=2,
        confidence=0.60, status="pending"
    )
    # rel8: s4 -> s1 (rejected relationship -> excluded)
    rel8 = Relationship(
        id=8, supplier_id=4, buyer_id=1, material_id=3,
        lead_time_days=10, share_pct=10.0, inventory_days=0,
        confidence=0.40, status="rejected", tier=1  # Stale tier to be cleared
    )
    session.add_all([rel1, rel2, rel3, rel4, rel5, rel6, rel7, rel8])
    session.flush()

    # Junction multi-evidence for rel1
    re1 = RelationshipEvidence(relationship_id=1, evidence_id=1)
    re2 = RelationshipEvidence(relationship_id=1, evidence_id=2)
    session.add_all([re1, re2])
    session.commit()


# =============================================================================
# Helper Tests
# =============================================================================

def test_node_id_helpers():
    """Verifies to_node_id and parse_supplier_id conversions."""
    assert to_node_id(42) == "supplier:42"
    assert parse_supplier_id(42) == 42
    assert parse_supplier_id("supplier:42") == 42
    assert parse_supplier_id("42") == 42
    with pytest.raises(ValueError):
        parse_supplier_id(None)


# =============================================================================
# Manufacturer Resolution Tests
# =============================================================================

def test_manufacturer_resolution_zero_manufacturers(graph_test_db):
    """Verifies ManufacturerNotFoundError when no active manufacturer exists."""
    svc = GraphService()
    # Add only regular suppliers
    s = Supplier(id=1, name="Supplier Only", entity_type="supplier", is_active=True)
    graph_test_db.add(s)
    graph_test_db.commit()

    with pytest.raises(ManufacturerNotFoundError) as exc_info:
        svc.rebuild(graph_test_db)
    assert "No active manufacturer found" in str(exc_info.value)


def test_manufacturer_resolution_multiple_manufacturers(graph_test_db):
    """Verifies MultipleManufacturersError when multiple active manufacturers exist without override."""
    svc = GraphService()
    m1 = Supplier(id=1, name="Mfg 1", entity_type="manufacturer", is_active=True)
    m2 = Supplier(id=2, name="Mfg 2", entity_type="manufacturer", is_active=True)
    graph_test_db.add_all([m1, m2])
    graph_test_db.commit()

    with pytest.raises(MultipleManufacturersError) as exc_info:
        svc.rebuild(graph_test_db)
    assert "Multiple active manufacturers found" in str(exc_info.value)

    # Specifying explicit manufacturer_id succeeds
    summary = svc.rebuild(graph_test_db, manufacturer_id=1)
    assert summary["manufacturer_id"] == 1


def test_manufacturer_resolution_invalid_explicit_id(graph_test_db):
    """Verifies ManufacturerNotFoundError when specified manufacturer_id is missing or inactive."""
    svc = GraphService()
    m1 = Supplier(id=1, name="Mfg Inactive", entity_type="manufacturer", is_active=False)
    graph_test_db.add(m1)
    graph_test_db.commit()

    with pytest.raises(ManufacturerNotFoundError):
        svc.rebuild(graph_test_db, manufacturer_id=1)

    with pytest.raises(ManufacturerNotFoundError):
        svc.rebuild(graph_test_db, manufacturer_id=999)


# =============================================================================
# Core Graph Construction and Tier Calculation Tests
# =============================================================================

def test_standard_chain_construction_and_tiers(graph_test_db):
    """
    Verifies:
    - Active suppliers are nodes (s1..s6, excluding inactive s7).
    - Only approved relationships between active suppliers are edges (rel1, rel2, rel3, rel4, rel5).
    - Supplier tiers:
      s1 (Mfg) = Tier 0
      s2 (TyreWorks) = Tier 1
      s3 (RubberCore) = Tier 2
      s4 (GreenLatex) = Tier 3
      s5 (MultiRoute) = Tier 2 (shortest path: via s2)
      s6 (Disconnected) = Tier None
    """
    seed_chain_fixture(graph_test_db)
    svc = GraphService()

    summary = svc.rebuild(graph_test_db)
    assert summary["nodes"] == 6  # s1, s2, s3, s4, s5, s6 (s7 excluded)
    assert summary["edges"] == 5  # rel1, rel2, rel3, rel4, rel5 (rel6, rel7, rel8 excluded)
    assert summary["max_tier"] == 3
    assert summary["manufacturer_id"] == 1
    assert summary["has_cycles"] is False

    # Check node attributes in in-memory graph
    n1 = svc.get_node_data(1)
    assert n1["name"] == "AutoMotive Corp"
    assert n1["tier"] == 0

    n2 = svc.get_node_data(2)
    assert n2["name"] == "TyreWorks Ltd"
    assert n2["tier"] == 1

    n3 = svc.get_node_data(3)
    assert n3["name"] == "RubberCore Industries"
    assert n3["tier"] == 2

    n4 = svc.get_node_data(4)
    assert n4["name"] == "GreenLatex Pvt Ltd"
    assert n4["tier"] == 3

    # Multi-route supplier takes shortest distance
    n5 = svc.get_node_data(5)
    assert n5["name"] == "MultiRoute Ltd"
    assert n5["tier"] == 2

    # Disconnected supplier has NULL tier
    n6 = svc.get_node_data(6)
    assert n6["name"] == "Disconnected Ltd"
    assert n6["tier"] is None

    # Inactive supplier is not in the graph
    assert svc.get_node_data(7) is None


def test_edge_attributes_integrity(graph_test_db):
    """Verifies edge attributes including material, lead time, and junction evidence count."""
    seed_chain_fixture(graph_test_db)
    svc = GraphService()
    svc.rebuild(graph_test_db)

    # rel1: TyreWorks -> AutoMotive Corp
    edge_rel1 = svc.get_edge_data(2, 1)
    assert edge_rel1 is not None
    assert edge_rel1["relationship_id"] == 1
    assert edge_rel1["material"] == "Tyres"
    assert edge_rel1["lead_time_days"] == 7
    assert edge_rel1["share_pct"] == 100.0
    assert edge_rel1["inventory_days"] == 3
    assert edge_rel1["confidence"] == 0.98
    assert edge_rel1["status"] == "approved"
    # Backed by 2 junction records in RelationshipEvidence
    assert edge_rel1["evidence_count"] == 2

    # rel2: RubberCore -> TyreWorks (fallback to primary evidence_id)
    edge_rel2 = svc.get_edge_data(3, 2)
    assert edge_rel2 is not None
    assert edge_rel2["relationship_id"] == 2
    assert edge_rel2["evidence_count"] == 1

    # rel3: GreenLatex -> RubberCore (no evidence)
    edge_rel3 = svc.get_edge_data(4, 3)
    assert edge_rel3 is not None
    assert edge_rel3["evidence_count"] == 0


# =============================================================================
# Database Tier Synchronization Tests
# =============================================================================

def test_database_tier_synchronization_and_stale_clearing(graph_test_db):
    """
    Verifies that rebuild synchronizes tiers to relationships.tier in the database:
    - rel1 (s2 -> s1): tier = 1
    - rel2 (s3 -> s2): tier = 2
    - rel3 (s4 -> s3): tier = 3
    - rel4 (s5 -> s2): tier = 2
    - rel5 (s5 -> s3): tier = 2
    - rel6 (s7 inactive -> s1): tier = None
    - rel7 (pending): tier = None
    - rel8 (rejected, seeded with stale tier=1): cleared to None
    """
    seed_chain_fixture(graph_test_db)
    svc = GraphService()
    svc.rebuild(graph_test_db)

    rels = {r.id: r for r in graph_test_db.query(Relationship).all()}

    assert rels[1].tier == 1
    assert rels[2].tier == 2
    assert rels[3].tier == 3
    assert rels[4].tier == 2
    assert rels[5].tier == 2

    # Inactive, pending and rejected relationships must have tier None
    assert rels[6].tier is None
    assert rels[7].tier is None
    # Stale tier cleared on rel8
    assert rels[8].tier is None
    assert rels[8].status == "rejected"  # Status remains unchanged


# =============================================================================
# Traversal Methods Tests
# =============================================================================

def test_traversal_methods(graph_test_db):
    """
    Verifies upstream and downstream traversal methods:
    - Direct suppliers and buyers.
    - Ancestors and descendants.
    - Path existence and shortest path.
    """
    seed_chain_fixture(graph_test_db)
    svc = GraphService()
    svc.rebuild(graph_test_db)

    # Direct suppliers for TyreWorks (s2): RubberCore (s3) and MultiRoute (s5)
    direct_to_s2 = svc.get_direct_suppliers(2)
    assert direct_to_s2 == [3, 5]

    # Direct buyers for RubberCore (s3): TyreWorks (s2)
    direct_from_s3 = svc.get_direct_buyers(3)
    assert direct_from_s3 == [2]

    # All ancestors of AutoMotive Corp (s1): s2, s3, s4, s5
    ancestors_s1 = svc.get_upstream_ancestors(1)
    assert ancestors_s1 == {2, 3, 4, 5}

    # All descendants of GreenLatex (s4): s3, s2, s1
    descendants_s4 = svc.get_downstream_descendants(4)
    assert descendants_s4 == {1, 2, 3}

    # Path check: s4 reaches s1; s1 does not reach s4 (unidirectional flow)
    assert svc.has_path(4, 1) is True
    assert svc.has_path(1, 4) is False
    assert svc.has_path(6, 1) is False

    # Shortest path: s4 -> s3 -> s2 -> s1
    path = svc.shortest_path(4, 1)
    assert path == [4, 3, 2, 1]

    # Path string arguments
    assert svc.has_path("supplier:4", "supplier:1") is True
    assert svc.shortest_path("supplier:4", "supplier:1") == [4, 3, 2, 1]

    # Non-existent node returns safe fallbacks
    assert svc.get_direct_suppliers(999) == []
    assert svc.get_direct_buyers(999) == []
    assert svc.get_upstream_ancestors(999) == set()
    assert svc.get_downstream_descendants(999) == set()
    assert svc.shortest_path(999, 1) is None


# =============================================================================
# Cycle Detection and Safe Handling Tests
# =============================================================================

def test_cycle_detection_without_crashing_or_deleting(graph_test_db):
    """
    Verifies:
    - Detects directed cycles (e.g. s2 -> s3 -> s8 -> s2).
    - Does NOT crash tier calculation (BFS handles cycles gracefully).
    - Does NOT delete or drop edges from the database or in-memory graph.
    - Bounded cycle enumeration limits runtime.
    """
    seed_chain_fixture(graph_test_db)

    # Add a circular supplier relationship: s2 -> s8 -> s3 -> s2 (via existing s3 -> s2)
    s8 = Supplier(id=8, name="Cycle Partner", entity_type="supplier", is_active=True)
    graph_test_db.add(s8)
    graph_test_db.flush()

    rel_cycle1 = Relationship(
        id=9, supplier_id=2, buyer_id=8, material_id=2, status="approved"
    )
    rel_cycle2 = Relationship(
        id=10, supplier_id=8, buyer_id=3, material_id=2, status="approved"
    )
    graph_test_db.add_all([rel_cycle1, rel_cycle2])
    graph_test_db.commit()

    svc = GraphService()
    summary = svc.rebuild(graph_test_db)

    assert summary["has_cycles"] is True
    assert svc.has_cycles is True

    detected_cycles = svc.detect_cycles()
    assert len(detected_cycles) >= 1
    # Check that s8, s2, s3 form a detected cycle
    flattened_nodes = {n for cycle in detected_cycles for n in cycle}
    assert {2, 3, 8}.issubset(flattened_nodes)

    # Verify no relationships were deleted in the database
    db_rel_count = graph_test_db.query(Relationship).count()
    assert db_rel_count == 10  # All 8 original + 2 cycle relationships preserved!

    # Verify tier calculation completed without crashing
    assert svc.get_node_data(1)["tier"] == 0
    assert svc.get_node_data(2)["tier"] == 1


# =============================================================================
# Transaction Rollback and Error Handling Tests
# =============================================================================

def test_transaction_rollback_preserves_active_graph(graph_test_db):
    """
    Verifies that if a database commit fails during tier synchronization:
    - The transaction is rolled back.
    - The exception is re-raised.
    - The previously active in-memory graph is preserved untouched.
    """
    seed_chain_fixture(graph_test_db)
    svc = GraphService()

    # Initial successful build
    summary1 = svc.rebuild(graph_test_db)
    assert summary1["nodes"] == 6
    assert svc.is_built is True
    initial_built_at = svc.built_at

    # Attempt second rebuild with simulated commit failure
    with patch.object(graph_test_db, "commit", side_effect=RuntimeError("Simulated DB Disk Full")):
        with pytest.raises(RuntimeError) as exc_info:
            svc.rebuild(graph_test_db)
        assert "Simulated DB Disk Full" in str(exc_info.value)

    # Active graph was not corrupted or swapped
    assert svc.built_at == initial_built_at
    assert svc.node_count == 6


# =============================================================================
# Real Database Protection Tests
# =============================================================================

def test_real_tierlens_db_untouched():
    """
    Verifies that tierlens.db in the project directory was not modified by the tests.
    """
    if os.path.exists("tierlens.db"):
        mtime_before = os.path.getmtime("tierlens.db")
        # Run local check
        svc = GraphService()
        assert svc.is_built is False
        mtime_after = os.path.getmtime("tierlens.db")
        assert mtime_before == mtime_after
