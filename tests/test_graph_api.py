"""
Unit and integration tests for Graph and Dependency APIs (TASK-010).
Conforms to project-docs/API_SPEC.md Section 4.5.
Tests cover:
- Route registration on both root and /api/v1 paths.
- POST /graph/rebuild and manufacturer error handling.
- GET /graph node and edge generation, filters, and include_pending overlay.
- GET /graph/node/{node_type}/{id} supplier and line details, reaches, and evidence.
- GET /dependencies detection of shared_upstream_supplier and single_source_material.
- Risk handling (base_risk vs active alert score, empty breakdown in steady state).
- Protection of the real tierlens.db.
"""

import json
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import init_db
from backend.models.db import (
    Supplier,
    Material,
    Relationship,
    RelationshipEvidence,
    Evidence,
    Document,
    Plant,
    Product,
    ProductionLine,
    LineRequirement,
    DisruptionEvent,
    Alert,
    AlertAffectedNode,
)
from backend.graph.service import graph_service
from backend.api.graph import (
    rebuild_graph,
    get_graph,
    get_node_detail,
    get_dependencies,
)
from backend.models.schemas import (
    GraphResponse,
    GraphRebuildResponse,
    NodeDetailResponse,
    DependencyResponse,
)


@pytest.fixture
def graph_api_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with controlled test fixtures.
    """
    db_file = tmp_path / "test_graph_api_isolated.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    init_db(target_engine=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Materials
    m1 = Material(id=1, name="Tyres", material_type="assembly")
    m2 = Material(id=2, name="Rubber Seals", material_type="part")
    m3 = Material(id=3, name="Processed Rubber", material_type="part")
    m4 = Material(id=4, name="Natural Latex", material_type="raw")
    session.add_all([m1, m2, m3, m4])
    session.flush()

    # Documents & Evidence
    doc1 = Document(id=1, filename="PO_1042.pdf", doc_type="po", file_path="/tmp/po1.pdf")
    doc2 = Document(id=2, filename="Contract_01.txt", doc_type="contract", file_path="/tmp/c1.txt")
    session.add_all([doc1, doc2])
    session.flush()

    ev1 = Evidence(id=1, document_id=1, page=1, snippet="GreenLatex to supply Natural Latex", llm_confidence=0.92)
    ev2 = Evidence(id=2, document_id=2, page=1, snippet="RubberCore supplies Processed Rubber", llm_confidence=0.95)
    ev3 = Evidence(id=3, document_id=1, page=2, snippet="Secondary GreenLatex quality check", llm_confidence=0.88)
    session.add_all([ev1, ev2, ev3])
    session.flush()

    # Suppliers
    s1 = Supplier(id=1, name="AutoMotive Corp", entity_type="manufacturer", country="India", region="South Asia", base_risk=0.0, is_active=True)
    s2 = Supplier(id=2, name="TyreWorks Ltd", entity_type="supplier", country="India", region="South Asia", base_risk=15.0, is_active=True)
    s3 = Supplier(id=3, name="GripSeal Components", entity_type="supplier", country="India", region="South Asia", base_risk=10.0, is_active=True)
    s4 = Supplier(id=4, name="RubberCore Industries", entity_type="supplier", country="India", region="South Asia", base_risk=25.0, is_active=True)
    s5 = Supplier(id=5, name="GreenLatex Pvt Ltd", entity_type="supplier", country="India", region="South Asia", base_risk=35.0, is_active=True)
    s6 = Supplier(id=6, name="Disconnected Supplier", entity_type="supplier", country="Germany", region="Europe", base_risk=20.0, is_active=True)
    s7 = Supplier(id=7, name="Inactive Supplier", entity_type="supplier", country="India", region="South Asia", base_risk=50.0, is_active=False)
    session.add_all([s1, s2, s3, s4, s5, s6, s7])
    session.flush()

    # Plant, Product and Production Lines
    plant1 = Plant(id=1, manufacturer_id=1, name="Pune Assembly Plant", location="Pune, India")
    session.add(plant1)
    session.flush()

    prod1 = Product(id=1, name="Sedan X", unit_revenue=1200000.0)
    session.add(prod1)
    session.flush()

    line1 = ProductionLine(id=1, plant_id=1, product_id=1, name="Line A", units_per_day=50.0, daily_revenue=60000000.0)
    line2 = ProductionLine(id=2, plant_id=1, product_id=1, name="Line B", units_per_day=30.0, daily_revenue=36000000.0)
    session.add_all([line1, line2])
    session.flush()

    # Line Requirements: Line A requires Tyres (m1); Line B requires Rubber Seals (m2)
    lr1 = LineRequirement(line_id=1, material_id=1, qty_per_day=200.0, criticality="high", safety_stock_days=4)
    lr2 = LineRequirement(line_id=2, material_id=2, qty_per_day=120.0, criticality="high", safety_stock_days=5)
    session.add_all([lr1, lr2])
    session.flush()

    # Relationships:
    # rel1: TyreWorks (s2) -> AutoMotive (s1) (Tyres, approved) -> Tier 1
    rel1 = Relationship(id=1, supplier_id=2, buyer_id=1, material_id=1, lead_time_days=7, share_pct=100.0, confidence=0.98, status="approved")
    # rel2: GripSeal (s3) -> AutoMotive (s1) (Rubber Seals, approved) -> Tier 1
    rel2 = Relationship(id=2, supplier_id=3, buyer_id=1, material_id=2, lead_time_days=5, share_pct=100.0, confidence=0.98, status="approved")
    # rel3: RubberCore (s4) -> TyreWorks (s2) (Processed Rubber, approved) -> Tier 2
    rel3 = Relationship(id=3, supplier_id=4, buyer_id=2, material_id=3, lead_time_days=10, share_pct=75.0, confidence=0.95, status="approved", evidence_id=2)
    # rel4: RubberCore (s4) -> GripSeal (s3) (Processed Rubber, approved) -> Tier 2
    # RubberCore feeds BOTH Tier 1 suppliers (s2 and s3) -> Shared Upstream Supplier!
    rel4 = Relationship(id=4, supplier_id=4, buyer_id=3, material_id=3, lead_time_days=10, share_pct=85.0, confidence=0.95, status="approved")
    # rel5: GreenLatex (s5) -> RubberCore (s4) (Natural Latex, approved) -> Tier 3
    # GreenLatex is the ONLY supplier of Natural Latex -> Single Source Material!
    rel5 = Relationship(id=5, supplier_id=5, buyer_id=4, material_id=4, lead_time_days=21, share_pct=70.0, confidence=0.92, status="approved", evidence_id=1)
    # rel6: Pending relationship: GreenLatex (s5) -> TyreWorks (s2) (pending)
    rel6 = Relationship(id=6, supplier_id=5, buyer_id=2, material_id=4, lead_time_days=15, share_pct=30.0, confidence=0.60, status="pending")
    # rel7: Inactive relationship: Inactive Supplier (s7) -> AutoMotive (s1)
    rel7 = Relationship(id=7, supplier_id=7, buyer_id=1, material_id=1, status="approved")

    session.add_all([rel1, rel2, rel3, rel4, rel5, rel6, rel7])
    session.flush()

    # Multi-evidence link for rel5: backed by ev1 and ev3
    re1 = RelationshipEvidence(relationship_id=5, evidence_id=1)
    re2 = RelationshipEvidence(relationship_id=5, evidence_id=3)
    session.add_all([re1, re2])
    session.flush()

    # Active alert for GreenLatex (s5) to test alert risk score override and breakdown
    event1 = DisruptionEvent(
        id=1, supplier_id=5, event_type="shutdown", severity=5,
        start_date=date(2026, 11, 20), expected_duration_days=30, source="simulated", is_simulated=True
    )
    session.add(event1)
    session.flush()

    alert1 = Alert(
        id=1, event_id=1, severity_label="critical", risk_score=85.0,
        score_breakdown={"event_severity": 25, "criticality": 20, "single_source_exposure": 20, "buffer_gap": 15, "regional_risk": 5},
        status="open"
    )
    session.add(alert1)
    session.flush()

    # Alert affected node on Line A
    aan1 = AlertAffectedNode(alert_id=1, node_type="line", node_id=1, path_depth=3)
    session.add(aan1)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# Route Registration Tests
# =============================================================================

def test_graph_endpoint_routes_registered():
    """Verifies that all 4 endpoints are registered on both root and /api/v1 paths."""
    route_map = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}

    assert "/graph/rebuild" in route_map and "POST" in route_map["/graph/rebuild"]
    assert "/api/v1/graph/rebuild" in route_map and "POST" in route_map["/api/v1/graph/rebuild"]

    assert "/graph" in route_map and "GET" in route_map["/graph"]
    assert "/api/v1/graph" in route_map and "GET" in route_map["/api/v1/graph"]

    assert "/graph/node/{node_type}/{id}" in route_map and "GET" in route_map["/graph/node/{node_type}/{id}"]
    assert "/api/v1/graph/node/{node_type}/{id}" in route_map and "GET" in route_map["/api/v1/graph/node/{node_type}/{id}"]

    assert "/dependencies" in route_map and "GET" in route_map["/dependencies"]
    assert "/api/v1/dependencies" in route_map and "GET" in route_map["/api/v1/dependencies"]


# =============================================================================
# POST /graph/rebuild Tests
# =============================================================================

def test_post_graph_rebuild_success(graph_api_db):
    """Verifies POST /graph/rebuild computes tiers and returns correct node and edge summary."""
    res = rebuild_graph(db=graph_api_db)
    assert isinstance(res, GraphRebuildResponse)
    assert res.nodes == 6  # s1..s6 (s7 inactive excluded)
    assert res.edges == 5  # rel1..rel5 approved (rel6 pending, rel7 inactive excluded)
    assert res.max_tier == 3
    assert res.built_at is not None


def test_post_graph_rebuild_missing_manufacturer(graph_api_db):
    """Verifies 404 NOT_FOUND when no active manufacturer exists."""
    # Deactivate the manufacturer
    mfg = graph_api_db.query(Supplier).filter(Supplier.id == 1).first()
    mfg.is_active = False
    graph_api_db.commit()

    res = rebuild_graph(db=graph_api_db)
    assert res.status_code == 404
    body = json.loads(res.body.decode())
    assert body["error"]["code"] == "NOT_FOUND"


# =============================================================================
# GET /graph Tests
# =============================================================================

def test_get_graph_default_nodes_and_edges(graph_api_db):
    """
    Verifies GET /graph returns:
    - Supplier nodes (s1..s6) and production line nodes (line1, line2).
    - Approved edges only.
    - React Flow-compatible IDs: 'supplier:{id}', 'line:{id}', 'rel:{id}'.
    - Production line tiers = 0.
    """
    res = get_graph(db=graph_api_db)
    assert isinstance(res, GraphResponse)
    assert len(res.nodes) == 8  # 6 suppliers + 2 lines
    assert len(res.edges) == 5  # rel1..rel5

    node_map = {n.id: n for n in res.nodes}
    assert "supplier:1" in node_map
    assert node_map["supplier:1"].tier == 0
    assert "line:1" in node_map
    assert node_map["line:1"].tier == 0
    assert node_map["line:1"].type == "line"

    # GreenLatex has active alert risk score 85.0
    assert node_map["supplier:5"].risk_score == 85.0
    # TyreWorks has base_risk 15.0
    assert node_map["supplier:2"].risk_score == 15.0
    # Line A has active alert affected node score 85.0
    assert node_map["line:1"].risk_score == 85.0
    # Line B has risk score 0.0
    assert node_map["line:2"].risk_score == 0.0

    # RubberCore has flag 'hidden_dependency'
    assert "hidden_dependency" in node_map["supplier:4"].flags
    # GreenLatex has flag 'single_source'
    assert "single_source" in node_map["supplier:5"].flags

    edge_ids = {e.id for e in res.edges}
    assert "rel:1" in edge_ids
    assert "rel:5" in edge_ids
    assert all(e.status == "approved" for e in res.edges)


def test_get_graph_include_pending_overlay(graph_api_db):
    """Verifies include_pending=True adds pending edges as overlay without modifying operational graph."""
    res_no_pending = get_graph(include_pending=False, db=graph_api_db)
    assert len(res_no_pending.edges) == 5

    res_with_pending = get_graph(include_pending=True, db=graph_api_db)
    assert len(res_with_pending.edges) == 6  # 5 approved + 1 pending (rel6)

    pending_edge = next(e for e in res_with_pending.edges if e.id == "rel:6")
    assert pending_edge.status == "pending"
    assert pending_edge.source == "supplier:5"
    assert pending_edge.target == "supplier:2"

    # Operational graph in GraphService still has 5 edges
    assert graph_service.edge_count == 5


def test_get_graph_filters(graph_api_db):
    """Verifies query filters: tier_max, region, material_id, min_risk."""
    # 1. tier_max = 1 -> Only tier 0 (mfg, lines) and tier 1 (s2, s3)
    t1 = get_graph(tier_max=1, db=graph_api_db)
    tiers = {n.tier for n in t1.nodes if n.tier is not None}
    assert tiers.issubset({0, 1})

    # 2. region = 'Europe' -> only s6 (Disconnected Supplier)
    reg_eu = get_graph(region="Europe", db=graph_api_db)
    assert len(reg_eu.nodes) == 1
    assert reg_eu.nodes[0].id == "supplier:6"

    # 3. material_id = 4 (Natural Latex) -> only chains involving Natural Latex (s5 -> s4)
    mat4 = get_graph(material_id=4, db=graph_api_db)
    assert any(n.id == "supplier:5" for n in mat4.nodes)
    assert any(n.id == "supplier:4" for n in mat4.nodes)
    assert all(e.material == "Natural Latex" for e in mat4.edges)

    # 4. min_risk = 30.0 -> GreenLatex (85.0) and Line A (85.0)
    high_risk = get_graph(min_risk=30.0, db=graph_api_db)
    assert all(n.risk_score >= 30.0 for n in high_risk.nodes)


# =============================================================================
# GET /graph/node/{node_type}/{id} Tests
# =============================================================================

def test_get_node_detail_supplier_with_alert(graph_api_db):
    """
    Verifies supplier node detail for GreenLatex (s5):
    - Active alert risk score and score breakdown returned.
    - Upstream is empty.
    - Downstream has RubberCore.
    - Reaches: tier1_suppliers (TyreWorks, GripSeal), production_lines (Line A, Line B).
    - Multi-evidence deduplicated from relationship_evidence (ev1, ev3).
    """
    res = get_node_detail(node_type="supplier", id=5, db=graph_api_db)
    assert isinstance(res, NodeDetailResponse)
    assert res.id == "supplier:5"
    assert res.type == "supplier"
    assert res.label == "GreenLatex Pvt Ltd"
    assert res.tier == 3
    assert res.risk_score == 85.0
    assert res.risk_breakdown["event_severity"] == 25
    assert res.risk_breakdown["criticality"] == 20

    assert len(res.upstream) == 0
    assert len(res.downstream) == 1
    assert res.downstream[0].id == "supplier:4"
    assert res.downstream[0].label == "RubberCore Industries"
    assert res.downstream[0].material == "Natural Latex"

    assert set(res.reaches.tier1_suppliers) == {"TyreWorks Ltd", "GripSeal Components"}
    assert set(res.reaches.production_lines) == {"Line A", "Line B"}

    # Deduplicated evidence
    assert len(res.evidence) == 2
    snippets = {e.snippet for e in res.evidence}
    assert "GreenLatex to supply Natural Latex" in snippets
    assert "Secondary GreenLatex quality check" in snippets


def test_get_node_detail_evidence_excludes_unapproved_relationships(graph_api_db):
    """
    Verifies that evidence linked only to pending or rejected relationships is excluded
    from supplier node details, while evidence from approved relationships is preserved.
    """
    # Create evidence records
    ev_pending = Evidence(id=101, document_id=1, page=3, snippet="Unapproved pending contract quote", llm_confidence=0.5)
    ev_rejected = Evidence(id=102, document_id=1, page=4, snippet="Rejected vendor proposal snippet", llm_confidence=0.4)
    ev_junction_pending = Evidence(id=103, document_id=1, page=5, snippet="Junction pending evidence", llm_confidence=0.6)
    graph_api_db.add_all([ev_pending, ev_rejected, ev_junction_pending])
    graph_api_db.flush()

    # Create pending and rejected relationships incident to GreenLatex (s5)
    rel_pending = Relationship(
        id=101, supplier_id=5, buyer_id=1, material_id=4,
        lead_time_days=30, share_pct=10.0, confidence=0.5,
        status="pending", evidence_id=101,
    )
    rel_rejected = Relationship(
        id=102, supplier_id=5, buyer_id=3, material_id=4,
        lead_time_days=40, share_pct=5.0, confidence=0.4,
        status="rejected", evidence_id=102,
    )
    graph_api_db.add_all([rel_pending, rel_rejected])
    graph_api_db.flush()

    # Multi-evidence junction link for the pending relationship
    re_pending = RelationshipEvidence(relationship_id=101, evidence_id=103)
    graph_api_db.add(re_pending)
    graph_api_db.commit()

    # Fetch supplier 5 node detail
    res = get_node_detail(node_type="supplier", id=5, db=graph_api_db)
    assert isinstance(res, NodeDetailResponse)

    snippets = {e.snippet for e in res.evidence}
    # Approved evidence is present
    assert "GreenLatex to supply Natural Latex" in snippets
    assert "Secondary GreenLatex quality check" in snippets
    # Unapproved evidence is strictly excluded
    assert "Unapproved pending contract quote" not in snippets
    assert "Rejected vendor proposal snippet" not in snippets
    assert "Junction pending evidence" not in snippets


def test_get_node_detail_supplier_without_alert_empty_breakdown(graph_api_db):
    """Verifies supplier with no active alert returns base_risk and empty risk_breakdown."""
    res = get_node_detail(node_type="supplier", id=2, db=graph_api_db)
    assert isinstance(res, NodeDetailResponse)
    assert res.id == "supplier:2"
    assert res.risk_score == 15.0  # base_risk
    assert res.risk_breakdown == {}  # Empty breakdown in steady state (no alert)


def test_get_node_detail_production_line(graph_api_db):
    """Verifies line node detail for Line A."""
    res = get_node_detail(node_type="line", id=1, db=graph_api_db)
    assert isinstance(res, NodeDetailResponse)
    assert res.id == "line:1"
    assert res.type == "line"
    assert res.label == "Line A (Sedan X)"
    assert res.tier == 0
    assert res.risk_score == 85.0  # Alert on Line A

    # Upstream has TyreWorks supplying Tyres
    assert len(res.upstream) == 1
    assert res.upstream[0].id == "supplier:2"
    assert res.upstream[0].material == "Tyres"

    assert res.downstream == []
    assert res.reaches.production_lines == ["Line A"]


def test_get_node_detail_validation_and_not_found(graph_api_db):
    """Verifies 422 on invalid node_type and 404 on missing record."""
    # Invalid node_type
    res_inv = get_node_detail(node_type="invalid_type", id=1, db=graph_api_db)
    assert res_inv.status_code == 422
    body = json.loads(res_inv.body.decode())
    assert body["error"]["code"] == "VALIDATION_ERROR"

    # Missing supplier
    res_missing = get_node_detail(node_type="supplier", id=999, db=graph_api_db)
    assert res_missing.status_code == 404

    # Missing line
    res_missing_line = get_node_detail(node_type="line", id=999, db=graph_api_db)
    assert res_missing_line.status_code == 404

    # Inactive supplier returns 404
    res_inactive = get_node_detail(node_type="supplier", id=7, db=graph_api_db)
    assert res_inactive.status_code == 404


# =============================================================================
# GET /dependencies Tests
# =============================================================================

def test_get_dependencies_detection(graph_api_db):
    """
    Verifies detection of:
    - shared_upstream_supplier: RubberCore (s4) feeding TyreWorks (s2) and GripSeal (s3).
    - single_source_material: Natural Latex supplied solely by GreenLatex (s5).
    """
    res = get_dependencies(db=graph_api_db)
    assert isinstance(res, DependencyResponse)
    assert res.total == 2

    shared = next(d for d in res.items if d.type == "shared_upstream_supplier")
    assert shared.supplier.id == 4
    assert shared.supplier.name == "RubberCore Industries"
    assert set(shared.affected_tier1) == {"TyreWorks Ltd", "GripSeal Components"}
    assert set(shared.affected_lines) == {"Line A", "Line B"}
    assert shared.severity == "high"

    single = next(d for d in res.items if d.type == "single_source_material")
    assert single.material.name == "Natural Latex"
    assert single.supplier.id == 5
    assert single.supplier.name == "GreenLatex Pvt Ltd"
    assert single.severity == "high"


def test_get_dependencies_filtering(graph_api_db):
    """Verifies filtering dependencies by type and min_severity."""
    # Filter by type: shared_upstream_supplier
    res_shared = get_dependencies(type="shared_upstream_supplier", db=graph_api_db)
    assert res_shared.total == 1
    assert res_shared.items[0].type == "shared_upstream_supplier"

    # Filter by min_severity: critical (none are critical)
    res_crit = get_dependencies(min_severity="critical", db=graph_api_db)
    assert res_crit.total == 0

    # Filter by min_severity: high (both are high)
    res_high = get_dependencies(min_severity="high", db=graph_api_db)
    assert res_high.total == 2


def test_single_source_material_tier1_coexists_with_tier2(graph_api_db):
    """
    Verifies that a raw material supplied by one Tier 1 supplier AND one Tier 2+ supplier
    is still correctly detected as single-source at Tier 2+ (Tier 1 is ignored in count).
    """
    # Create a new raw material: Raw Silica
    mat_silica = Material(id=10, name="Raw Silica", material_type="raw", unit="MT", category="minerals")
    graph_api_db.add(mat_silica)
    graph_api_db.flush()

    # s2 (TyreWorks, Tier 1) supplies Raw Silica directly to manufacturer s1 (Tier 1 relationship)
    rel_t1 = Relationship(
        id=201, supplier_id=2, buyer_id=1, material_id=10,
        lead_time_days=7, share_pct=40.0, confidence=0.95, status="approved"
    )
    # s4 (RubberCore, Tier 2) supplies Raw Silica to TyreWorks s2 (Tier 2 relationship)
    rel_t2 = Relationship(
        id=202, supplier_id=4, buyer_id=2, material_id=10,
        lead_time_days=14, share_pct=60.0, confidence=0.92, status="approved"
    )
    graph_api_db.add_all([rel_t1, rel_t2])
    graph_api_db.commit()

    # Rebuild graph to register the new material edges and synchronize tiers
    graph_service.rebuild(graph_api_db)

    res = get_dependencies(type="single_source_material", db=graph_api_db)
    assert isinstance(res, DependencyResponse)

    # Both Natural Latex (s5, tier 3) and Raw Silica (s4, tier 2) should be detected
    silica_dep = next((d for d in res.items if d.material and d.material.name == "Raw Silica"), None)
    assert silica_dep is not None
    assert silica_dep.supplier.id == 4
    assert silica_dep.supplier.name == "RubberCore Industries"
    assert silica_dep.supplier.tier == 2
    assert silica_dep.severity == "high"


def test_single_source_material_multiple_tier2_suppliers_not_flagged(graph_api_db):
    """
    Verifies that a raw material supplied by multiple Tier 2+ suppliers
    is NOT flagged as a single-source material vulnerability.
    """
    # Create a new raw material: Crude Oil
    mat_oil = Material(id=11, name="Crude Oil", material_type="raw", unit="barrels", category="energy")
    # Create another Tier 2+ supplier s8
    s8 = Supplier(
        id=8, name="Global PetroChem", entity_type="supplier",
        country="India", region="South Asia", base_risk=20.0, is_active=True
    )
    graph_api_db.add_all([mat_oil, s8])
    graph_api_db.flush()

    # Both s4 (RubberCore, Tier 2) and s8 (Global PetroChem, Tier 2) supply Crude Oil to s2 (Tier 1)
    rel_oil1 = Relationship(
        id=203, supplier_id=4, buyer_id=2, material_id=11,
        lead_time_days=10, share_pct=50.0, confidence=0.95, status="approved"
    )
    rel_oil2 = Relationship(
        id=204, supplier_id=8, buyer_id=2, material_id=11,
        lead_time_days=12, share_pct=50.0, confidence=0.90, status="approved"
    )
    graph_api_db.add_all([rel_oil1, rel_oil2])
    graph_api_db.commit()

    graph_service.rebuild(graph_api_db)

    res = get_dependencies(type="single_source_material", db=graph_api_db)
    assert isinstance(res, DependencyResponse)

    # Crude Oil must NOT be flagged because it has 2 distinct Tier 2+ suppliers
    oil_dep = next((d for d in res.items if d.material and d.material.name == "Crude Oil"), None)
    assert oil_dep is None


