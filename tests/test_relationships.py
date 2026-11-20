"""
Unit and integration tests for the Relationship Management API (TASK-007):
- GET /relationships
- GET /review-queue
- POST /review/{relationship_id}

Tests all query filters, pagination, evidence counting, review queue ordering,
approval, rejection, corrections, validation errors, and missing IDs using an
isolated SQLite database.
"""

import pytest
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from backend.main import app
from backend.database import Base, init_db
from backend.api.relationships import (
    list_relationships,
    get_review_queue,
    review_relationship,
)
from backend.models.db import (
    Document,
    Supplier,
    Material,
    Evidence,
    Relationship,
    RelationshipEvidence,
)
from backend.models.schemas import (
    RelationshipListResponse,
    RelationshipListItem,
    ReviewQueueResponse,
    ReviewQueueItem,
    ReviewRequest,
    ReviewCorrections,
    ReviewResponse,
)


@pytest.fixture
def rel_test_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with controlled test fixtures.
    Ensures init_db creates all tables and the review_queue view.
    """
    db_file = tmp_path / "test_relationships_isolated.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False}
    )
    init_db(target_engine=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Documents
    doc1 = Document(
        id=1, filename="PO_1042.pdf", doc_type="purchase_order",
        file_path="/tmp/PO_1042.pdf", extraction_status="done"
    )
    doc2 = Document(
        id=2, filename="Procurement_Note_07.txt", doc_type="procurement_note",
        file_path="/tmp/Procurement_Note_07.txt", extraction_status="done"
    )
    session.add_all([doc1, doc2])
    session.flush()

    # Suppliers
    s1 = Supplier(id=1, name="AutoMotive Corp", entity_type="manufacturer", is_active=True)
    s2 = Supplier(id=2, name="TyreWorks Ltd", entity_type="supplier", is_active=True)
    s3 = Supplier(id=3, name="RubberCore Industries", entity_type="supplier", is_active=True)
    session.add_all([s1, s2, s3])
    session.flush()

    # Materials
    m1 = Material(id=1, name="Tyres", material_type="part")
    m2 = Material(id=2, name="Natural Latex", material_type="raw")
    session.add_all([m1, m2])
    session.flush()

    # Evidence records
    ev1 = Evidence(id=1, document_id=1, page=1, snippet="Tyres PO snippet", llm_confidence=0.98)
    ev2 = Evidence(id=2, document_id=2, page=1, snippet="Natural latex pending note", llm_confidence=0.58)
    ev3 = Evidence(id=3, document_id=2, page=1, snippet="Secondary latex procurement note", llm_confidence=0.75)
    session.add_all([ev1, ev2, ev3])
    session.flush()

    # Relationships:
    # 1. Approved relationship: s2 -> s1 (Tyres), tier 1, confidence 0.98, evidence_id=1
    #    Backed by 2 junction records in RelationshipEvidence -> evidence_count = 2
    rel1 = Relationship(
        id=1, supplier_id=2, buyer_id=1, material_id=1,
        tier=1, lead_time_days=10, share_pct=80.0, inventory_days=5,
        confidence=0.98, status="approved", evidence_id=1
    )
    # 2. Pending relationship: s3 -> s2 (Natural Latex), tier 2, confidence 0.58, evidence_id=2
    #    No junction table records -> fallback evidence_count = 1
    rel2 = Relationship(
        id=2, supplier_id=3, buyer_id=2, material_id=2,
        tier=2, lead_time_days=20, share_pct=60.0, inventory_days=10,
        confidence=0.58, status="pending", evidence_id=2
    )
    # 3. Pending relationship: s3 -> s1 (Natural Latex), tier 3, confidence 0.75, evidence_id=3
    #    No junction table records -> fallback evidence_count = 1
    rel3 = Relationship(
        id=3, supplier_id=3, buyer_id=1, material_id=2,
        tier=3, lead_time_days=15, share_pct=40.0, inventory_days=0,
        confidence=0.75, status="pending", evidence_id=3
    )
    session.add_all([rel1, rel2, rel3])
    session.flush()

    # Multi-evidence link for rel1
    rel_ev1 = RelationshipEvidence(relationship_id=1, evidence_id=1)
    rel_ev2 = RelationshipEvidence(relationship_id=1, evidence_id=3)
    session.add_all([rel_ev1, rel_ev2])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# Route Registration Tests
# =============================================================================

def test_relationship_endpoint_routes_registered():
    """Verifies that relationships, review-queue and review routes are registered on both paths."""
    route_map = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}

    assert "/relationships" in route_map
    assert "GET" in route_map["/relationships"]
    assert "/api/v1/relationships" in route_map
    assert "GET" in route_map["/api/v1/relationships"]

    assert "/review-queue" in route_map
    assert "GET" in route_map["/review-queue"]
    assert "/api/v1/review-queue" in route_map
    assert "GET" in route_map["/api/v1/review-queue"]

    assert "/review/{relationship_id}" in route_map
    assert "POST" in route_map["/review/{relationship_id}"]
    assert "/api/v1/review/{relationship_id}" in route_map
    assert "POST" in route_map["/api/v1/review/{relationship_id}"]


# =============================================================================
# GET /relationships Tests
# =============================================================================

def test_list_relationships_default(rel_test_db):
    """Verifies default listing returns all relationships with nested objects and correct evidence count."""
    res = list_relationships(limit=50, offset=0, db=rel_test_db)
    assert isinstance(res, RelationshipListResponse)
    assert res.total == 3
    assert len(res.items) == 3

    # Check nested party & material structures
    item1 = next(i for i in res.items if i.id == 1)
    assert item1.supplier.id == 2
    assert item1.supplier.name == "TyreWorks Ltd"
    assert item1.buyer.id == 1
    assert item1.buyer.name == "AutoMotive Corp"
    assert item1.material.id == 1
    assert item1.material.name == "Tyres"
    assert item1.status == "approved"
    assert item1.tier == 1
    # Multi-document junction count
    assert item1.evidence_count == 2

    # Check fallback evidence count for rel2
    item2 = next(i for i in res.items if i.id == 2)
    assert item2.status == "pending"
    assert item2.evidence_count == 1


def test_list_relationships_status_filter(rel_test_db):
    """Tests filtering by relationship status ('pending', 'approved', 'rejected')."""
    pending = list_relationships(status="pending", limit=50, offset=0, db=rel_test_db)
    assert pending.total == 2
    assert {i.id for i in pending.items} == {2, 3}

    approved = list_relationships(status="approved", limit=50, offset=0, db=rel_test_db)
    assert approved.total == 1
    assert approved.items[0].id == 1

    rejected = list_relationships(status="rejected", limit=50, offset=0, db=rel_test_db)
    assert rejected.total == 0
    assert len(rejected.items) == 0


def test_list_relationships_tier_filter(rel_test_db):
    """Tests filtering by tier."""
    t1 = list_relationships(tier=1, limit=50, offset=0, db=rel_test_db)
    assert t1.total == 1
    assert t1.items[0].id == 1

    t2 = list_relationships(tier=2, limit=50, offset=0, db=rel_test_db)
    assert t2.total == 1
    assert t2.items[0].id == 2

    t99 = list_relationships(tier=99, limit=50, offset=0, db=rel_test_db)
    assert t99.total == 0


def test_list_relationships_material_and_supplier_filters(rel_test_db):
    """Tests filtering by material_id and supplier_id."""
    # Material 1 (Tyres) -> rel1
    m1 = list_relationships(material_id=1, limit=50, offset=0, db=rel_test_db)
    assert m1.total == 1
    assert m1.items[0].id == 1

    # Material 2 (Natural Latex) -> rel2, rel3
    m2 = list_relationships(material_id=2, limit=50, offset=0, db=rel_test_db)
    assert m2.total == 2
    assert {i.id for i in m2.items} == {2, 3}

    # Supplier 2 (TyreWorks Ltd) -> rel1
    s2 = list_relationships(supplier_id=2, limit=50, offset=0, db=rel_test_db)
    assert s2.total == 1
    assert s2.items[0].id == 1

    # Supplier 3 (RubberCore Industries) -> rel2, rel3
    s3 = list_relationships(supplier_id=3, limit=50, offset=0, db=rel_test_db)
    assert s3.total == 2
    assert {i.id for i in s3.items} == {2, 3}


def test_list_relationships_min_confidence_filter(rel_test_db):
    """Tests filtering by minimum confidence."""
    # min_confidence 0.70 -> rel1 (0.98) and rel3 (0.75)
    c70 = list_relationships(min_confidence=0.70, limit=50, offset=0, db=rel_test_db)
    assert c70.total == 2
    assert {i.id for i in c70.items} == {1, 3}

    # min_confidence 0.90 -> only rel1 (0.98)
    c90 = list_relationships(min_confidence=0.90, limit=50, offset=0, db=rel_test_db)
    assert c90.total == 1
    assert c90.items[0].id == 1


def test_list_relationships_pagination(rel_test_db):
    """Tests limit, offset and total count logic."""
    p1 = list_relationships(limit=2, offset=0, db=rel_test_db)
    assert p1.total == 3
    assert len(p1.items) == 2
    assert p1.items[0].id == 1
    assert p1.items[1].id == 2

    p2 = list_relationships(limit=2, offset=2, db=rel_test_db)
    assert p2.total == 3
    assert len(p2.items) == 1
    assert p2.items[0].id == 3

    p3 = list_relationships(limit=2, offset=10, db=rel_test_db)
    assert p3.total == 3
    assert len(p3.items) == 0


# =============================================================================
# GET /review-queue Tests
# =============================================================================

def test_get_review_queue_retrieval_and_ordering(rel_test_db):
    """
    Verifies:
    - Queries review_queue view returning only pending relationships.
    - Flat structure with relationship_id, supplier, buyer, material, confidence, snippet, document.
    - Explicit ascending order by confidence (lowest confidence first).
    """
    res = get_review_queue(db=rel_test_db)
    assert isinstance(res, ReviewQueueResponse)
    assert res.total == 2
    assert len(res.items) == 2

    # Lowest confidence first: rel2 (0.58) before rel3 (0.75)
    first = res.items[0]
    second = res.items[1]
    assert first.relationship_id == 2
    assert first.confidence == 0.58
    assert first.supplier == "RubberCore Industries"
    assert first.buyer == "TyreWorks Ltd"
    assert first.material == "Natural Latex"
    assert first.snippet == "Natural latex pending note"
    assert first.document == "Procurement_Note_07.txt"

    assert second.relationship_id == 3
    assert second.confidence == 0.75


def test_get_review_queue_empty_when_all_reviewed(rel_test_db):
    """Verifies review-queue returns items: [], total: 0 when no pending relationships remain."""
    # Approve both pending relationships
    review_relationship(relationship_id=2, body=ReviewRequest(action="approve"), db=rel_test_db)
    review_relationship(relationship_id=3, body=ReviewRequest(action="approve"), db=rel_test_db)

    res = get_review_queue(db=rel_test_db)
    assert res.total == 0
    assert len(res.items) == 0


# =============================================================================
# POST /review/{relationship_id} Tests
# =============================================================================

def test_review_relationship_approve(rel_test_db):
    """Verifies approval updates status, reviewed_by, reviewed_at and flags graph rebuild."""
    res = review_relationship(
        relationship_id=2,
        body=ReviewRequest(action="approve", reviewed_by="analyst_1"),
        db=rel_test_db,
    )
    assert isinstance(res, ReviewResponse)
    assert res.id == 2
    assert res.status == "approved"
    assert res.graph_rebuild_required is True

    # Verify database state
    row = rel_test_db.query(Relationship).filter(Relationship.id == 2).first()
    assert row.status == "approved"
    assert row.reviewed_by == "analyst_1"
    assert row.reviewed_at is not None


def test_review_relationship_approve_with_corrections(rel_test_db):
    """Verifies corrections (share_pct, lead_time_days) are applied before approval."""
    res = review_relationship(
        relationship_id=3,
        body=ReviewRequest(
            action="approve",
            corrections=ReviewCorrections(share_pct=65.0, lead_time_days=12),
            reviewed_by="analyst_senior",
        ),
        db=rel_test_db,
    )
    assert res.id == 3
    assert res.status == "approved"

    # Verify updated fields in database
    row = rel_test_db.query(Relationship).filter(Relationship.id == 3).first()
    assert row.status == "approved"
    assert row.share_pct == 65.0
    assert row.lead_time_days == 12
    assert row.reviewed_by == "analyst_senior"


def test_review_relationship_reject(rel_test_db):
    """Verifies rejection updates status to rejected."""
    res = review_relationship(
        relationship_id=2,
        body=ReviewRequest(action="reject", reviewed_by="qa_inspector"),
        db=rel_test_db,
    )
    assert res.id == 2
    assert res.status == "rejected"
    assert res.graph_rebuild_required is True

    row = rel_test_db.query(Relationship).filter(Relationship.id == 2).first()
    assert row.status == "rejected"
    assert row.reviewed_by == "qa_inspector"


def test_review_relationship_reject_with_corrections_fails_422(rel_test_db):
    """Verifies rejection with corrections returns 422 VALIDATION_ERROR."""
    res = review_relationship(
        relationship_id=2,
        body=ReviewRequest(
            action="reject",
            corrections=ReviewCorrections(share_pct=50.0),
        ),
        db=rel_test_db,
    )
    assert res.status_code == 422
    body = json.loads(res.body.decode())
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "corrections" in body["error"]["details"]


def test_review_relationship_not_found(rel_test_db):
    """Verifies 404 NOT_FOUND when relationship ID does not exist."""
    res = review_relationship(
        relationship_id=999,
        body=ReviewRequest(action="approve"),
        db=rel_test_db,
    )
    assert res.status_code == 404
    body = json.loads(res.body.decode())
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Relationship 999 does not exist."


def test_review_relationship_invalid_id_422(rel_test_db):
    """Verifies 422 VALIDATION_ERROR when relationship_id < 1."""
    res = review_relationship(
        relationship_id=0,
        body=ReviewRequest(action="approve"),
        db=rel_test_db,
    )
    assert res.status_code == 422
    body = json.loads(res.body.decode())
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_review_corrections_unknown_field_rejected():
    """Verifies that unknown correction fields are rejected by Pydantic extra='forbid'."""
    with pytest.raises(ValidationError):
        ReviewCorrections(share_pct=50.0, unknown_field="invalid")


def test_review_corrections_out_of_bounds_rejected():
    """Verifies share_pct bounds (0-100) and lead_time_days bounds (>= 0)."""
    with pytest.raises(ValidationError):
        ReviewCorrections(share_pct=150.0)

    with pytest.raises(ValidationError):
        ReviewCorrections(share_pct=-5.0)

    with pytest.raises(ValidationError):
        ReviewCorrections(lead_time_days=-1)
