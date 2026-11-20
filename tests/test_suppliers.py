"""
Unit and integration tests for the Supplier Management API: GET /suppliers.
Tests route registration, schemas, filtering, pagination, materials aggregation,
tier/risk calculations, error handling, and parameter constraints on an isolated database.
"""

import pytest
import json
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.exceptions import RequestValidationError
from fastapi import Request

from backend.main import app, validation_exception_handler
from backend.api.suppliers import list_suppliers, get_supplier
from backend.models.db import (
    Base,
    Supplier,
    SupplierAlias,
    Material,
    SupplierMaterial,
    Relationship,
    DisruptionEvent,
    Alert,
)
from backend.models.schemas import (
    SupplierListResponse,
    SupplierListItem,
    SupplierDetailResponse,
    SupplierDetailSupplied,
    SupplierDetailMaterial,
)


@pytest.fixture
def test_db_session(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with controlled fixture data.
    Never modifies the development database.
    """
    db_file = tmp_path / "test_suppliers_isolated.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Seed test materials
    m_latex = Material(id=1, name="Natural Latex", material_type="raw")
    m_rubber = Material(id=2, name="Synthetic Rubber", material_type="raw")
    m_carbon = Material(id=3, name="Carbon Black", material_type="raw")
    session.add_all([m_latex, m_rubber, m_carbon])

    # Seed test suppliers
    # 1: Active, Tier 1, no alert -> base_risk 20.0
    s1 = Supplier(
        id=1, name="Alpha Corp", country="Japan", region="East Asia",
        base_risk=20.0, is_active=True
    )
    # 2: Active, Tier 2, has alert -> effective_risk 75.0 (overriding base_risk 35.0)
    s2 = Supplier(
        id=2, name="Beta Latex Ltd", country="India", region="South Asia",
        capacity_per_month=120.0, base_risk=35.0, is_active=True
    )
    # 3: Active, Null Tier (no tier assigned), no alert -> base_risk 15.0
    s3 = Supplier(
        id=3, name="Gamma Rubber", country="India", region="South Asia",
        base_risk=15.0, is_active=True
    )
    # 4: Inactive supplier (should never be returned)
    s4 = Supplier(
        id=4, name="Delta Inactive", country="India", region="South Asia",
        base_risk=50.0, is_active=False
    )
    session.add_all([s1, s2, s3, s4])
    session.flush()

    # Aliases for s2 (inserted out of alphabetical order to test sorting)
    a1 = SupplierAlias(supplier_id=2, alias="Beta Ltd")
    a2 = SupplierAlias(supplier_id=2, alias="Beta Latex")
    session.add_all([a1, a2])

    # Capabilities: s1 can supply Carbon Black
    sm1 = SupplierMaterial(supplier_id=1, material_id=3, is_qualified=True)
    # Capabilities: s2 can supply Natural Latex
    sm2 = SupplierMaterial(supplier_id=2, material_id=1, is_qualified=True)
    session.add_all([sm1, sm2])

    # Outgoing relationships:
    # s1 supplies Natural Latex to s2 (tier=1, approved) -> s1 has materials ["Carbon Black", "Natural Latex"]
    rel1 = Relationship(
        id=1, supplier_id=1, buyer_id=2, material_id=1,
        tier=1, status="approved"
    )
    # s2 supplies Synthetic Rubber to s3 (tier=2, approved) -> s2 has materials ["Natural Latex", "Synthetic Rubber"]
    rel2 = Relationship(
        id=2, supplier_id=2, buyer_id=3, material_id=2,
        tier=2, status="approved"
    )
    # s3 supplies Carbon Black to s1 (tier=None, approved) -> s3 has null tier
    rel3 = Relationship(
        id=3, supplier_id=3, buyer_id=1, material_id=3,
        tier=None, status="approved"
    )
    session.add_all([rel1, rel2, rel3])

    # Disruption Event and Alert for s2: risk_score 75.0
    event = DisruptionEvent(
        id=1, supplier_id=2, event_type="shutdown", severity=4,
        start_date=date(2026, 11, 20), is_simulated=True
    )
    session.add(event)
    session.flush()

    alert = Alert(
        id=1, event_id=1, severity_label="high", risk_score=75.0,
        score_breakdown={"event_severity": 30, "criticality": 45},
        status="open", created_at=datetime(2026, 11, 20, 10, 0, 0)
    )
    session.add(alert)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_endpoint_routes_registered():
    """Verifies that both /suppliers and /api/v1/suppliers are registered routes."""
    route_map = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}
    assert "/suppliers" in route_map, "/suppliers route is not registered"
    assert "GET" in route_map["/suppliers"]
    assert "/api/v1/suppliers" in route_map, "/api/v1/suppliers route is not registered"
    assert "GET" in route_map["/api/v1/suppliers"]


def test_list_suppliers_default(test_db_session):
    """Verifies default retrieval returns all active suppliers with correct structure."""
    res = list_suppliers(limit=50, offset=0, db=test_db_session)
    assert isinstance(res, SupplierListResponse)
    assert res.total == 3  # s1, s2, s3 (s4 is inactive)
    assert len(res.items) == 3
    assert res.limit == 50
    assert res.offset == 0

    # Ensure items match schema
    for item in res.items:
        assert isinstance(item, SupplierListItem)
        assert item.id in (1, 2, 3)


def test_inactive_supplier_exclusion(test_db_session):
    """Confirms inactive suppliers are strictly excluded."""
    res = list_suppliers(limit=50, offset=0, db=test_db_session)
    ids = [item.id for item in res.items]
    assert 4 not in ids, "Inactive supplier 4 was included in results"


def test_name_search_filtering(test_db_session):
    """Tests case-insensitive substring search on supplier name (q parameter)."""
    # Lowercase match
    res = list_suppliers(q="latex", limit=50, offset=0, db=test_db_session)
    assert res.total == 1
    assert res.items[0].name == "Beta Latex Ltd"

    # Uppercase match
    res_upper = list_suppliers(q="LATEX", limit=50, offset=0, db=test_db_session)
    assert res_upper.total == 1
    assert res_upper.items[0].name == "Beta Latex Ltd"

    # Substring match
    res_sub = list_suppliers(q="corp", limit=50, offset=0, db=test_db_session)
    assert res_sub.total == 1
    assert res_sub.items[0].name == "Alpha Corp"

    # Non-matching
    res_none = list_suppliers(q="nonexistent", limit=50, offset=0, db=test_db_session)
    assert res_none.total == 0
    assert len(res_none.items) == 0


def test_region_filtering(test_db_session):
    """Tests case-insensitive exact match on supplier region."""
    # South Asia (matches s2, s3)
    res_sa = list_suppliers(region="south asia", limit=50, offset=0, db=test_db_session)
    assert res_sa.total == 2
    names = [i.name for i in res_sa.items]
    assert "Beta Latex Ltd" in names
    assert "Gamma Rubber" in names

    # East Asia (matches s1)
    res_ea = list_suppliers(region="EAST ASIA", limit=50, offset=0, db=test_db_session)
    assert res_ea.total == 1
    assert res_ea.items[0].name == "Alpha Corp"

    # No match
    res_empty = list_suppliers(region="Europe", limit=50, offset=0, db=test_db_session)
    assert res_empty.total == 0


def test_tier_filtering_and_null_tier(test_db_session):
    """Tests filtering by computed tier, and verifies null tier handling."""
    # Tier 1 (s1)
    res_t1 = list_suppliers(tier=1, limit=50, offset=0, db=test_db_session)
    assert res_t1.total == 1
    assert res_t1.items[0].id == 1
    assert res_t1.items[0].tier == 1

    # Tier 2 (s2)
    res_t2 = list_suppliers(tier=2, limit=50, offset=0, db=test_db_session)
    assert res_t2.total == 1
    assert res_t2.items[0].id == 2
    assert res_t2.items[0].tier == 2

    # Tier 3 (none match)
    res_t3 = list_suppliers(tier=3, limit=50, offset=0, db=test_db_session)
    assert res_t3.total == 0

    # Verify s3 has tier=None in default list
    res_all = list_suppliers(limit=50, offset=0, db=test_db_session)
    s3_item = next(i for i in res_all.items if i.id == 3)
    assert s3_item.tier is None


def test_risk_score_fallback_and_alert_override(test_db_session):
    """
    Verifies that:
    - Supplier with alert uses latest alert risk score (s2: 75.0, overriding base_risk 35.0)
    - Supplier without alert falls back to base_risk (s1: 20.0, s3: 15.0)
    """
    res = list_suppliers(limit=50, offset=0, db=test_db_session)
    scores = {i.id: i.risk_score for i in res.items}

    assert scores[1] == 20.0  # base_risk
    assert scores[2] == 75.0  # latest alert risk_score
    assert scores[3] == 15.0  # base_risk


def test_min_risk_filtering(test_db_session):
    """Tests min_risk filter using effective risk calculation."""
    # min_risk = 30.0 -> only s2 (75.0) matches
    res_30 = list_suppliers(min_risk=30.0, limit=50, offset=0, db=test_db_session)
    assert res_30.total == 1
    assert res_30.items[0].id == 2

    # min_risk = 20.0 -> s1 (20.0) and s2 (75.0) match
    res_20 = list_suppliers(min_risk=20.0, limit=50, offset=0, db=test_db_session)
    assert res_20.total == 2
    assert {i.id for i in res_20.items} == {1, 2}

    # min_risk = 80.0 -> none match
    res_80 = list_suppliers(min_risk=80.0, limit=50, offset=0, db=test_db_session)
    assert res_80.total == 0


def test_combined_filters(test_db_session):
    """Tests combining q, region, tier, and min_risk using AND logic."""
    # South Asia + latex + tier 2 + min_risk 50 -> matches s2
    res = list_suppliers(
        q="Latex", region="South Asia", tier=2, min_risk=50.0,
        limit=50, offset=0, db=test_db_session
    )
    assert res.total == 1
    assert res.items[0].id == 2

    # Same but tier 1 -> no match
    res_mismatch = list_suppliers(
        q="Latex", region="South Asia", tier=1, min_risk=50.0,
        limit=50, offset=0, db=test_db_session
    )
    assert res_mismatch.total == 0


def test_materials_aggregation_and_sorting(test_db_session):
    """
    Verifies materials are aggregated from capabilities AND outgoing relationships,
    deduplicated, and sorted alphabetically.
    """
    res = list_suppliers(limit=50, offset=0, db=test_db_session)
    items_by_id = {i.id: i for i in res.items}

    # s1: Capability has "Carbon Black", relationship has "Natural Latex"
    # Result: ["Carbon Black", "Natural Latex"] (alphabetical)
    assert items_by_id[1].materials == ["Carbon Black", "Natural Latex"]

    # s2: Capability has "Natural Latex", relationship has "Synthetic Rubber"
    # Result: ["Natural Latex", "Synthetic Rubber"]
    assert items_by_id[2].materials == ["Natural Latex", "Synthetic Rubber"]


def test_pagination_and_total_count(test_db_session):
    """Tests pagination limits, offsets, and total count calculations."""
    # Page 1: limit 2, offset 0 -> 2 items, total 3
    p1 = list_suppliers(limit=2, offset=0, db=test_db_session)
    assert p1.total == 3
    assert len(p1.items) == 2
    assert p1.limit == 2
    assert p1.offset == 0
    assert p1.items[0].id == 1
    assert p1.items[1].id == 2

    # Page 2: limit 2, offset 2 -> 1 item, total 3
    p2 = list_suppliers(limit=2, offset=2, db=test_db_session)
    assert p2.total == 3
    assert len(p2.items) == 1
    assert p2.items[0].id == 3

    # Page 3: offset beyond total -> 0 items, total 3
    p3 = list_suppliers(limit=2, offset=5, db=test_db_session)
    assert p3.total == 3
    assert len(p3.items) == 0


def test_openapi_parameter_constraints():
    """
    Verifies that the FastAPI OpenAPI schema documents the exact parameter constraints:
    limit (1-200, default 50), offset (>= 0, default 0), tier (>= 1), min_risk (0-100).
    """
    schema = app.openapi()
    params = schema["paths"]["/suppliers"]["get"]["parameters"]
    param_map = {p["name"]: p["schema"] for p in params}

    # limit: default 50, ge 1, le 200
    assert param_map["limit"]["default"] == 50
    assert param_map["limit"]["minimum"] == 1
    assert param_map["limit"]["maximum"] == 200

    # offset: default 0, ge 0
    assert param_map["offset"]["default"] == 0
    assert param_map["offset"]["minimum"] == 0

    # tier: minimum 1 (inside anyOf integer branch)
    tier_schema = next(s for s in param_map["tier"]["anyOf"] if s.get("type") == "integer")
    assert tier_schema["minimum"] == 1

    # min_risk: 0 to 100 (inside anyOf number branch)
    min_risk_schema = next(s for s in param_map["min_risk"]["anyOf"] if s.get("type") == "number")
    assert min_risk_schema["minimum"] == 0.0
    assert min_risk_schema["maximum"] == 100.0


def test_validation_error_handler_format():
    """
    Verifies that RequestValidationError returns the documented error envelope:
    {"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {...}}}
    """
    scope = {"type": "http", "method": "GET", "path": "/suppliers"}
    req = Request(scope=scope)
    err = RequestValidationError(errors=[{"loc": ["query", "limit"], "msg": "Input should be less than or equal to 200", "type": "less_than_equal"}])
    response = validation_exception_handler(req, err)

    assert response.status_code == 422
    import json
    data = json.loads(response.body.decode())
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "errors" in data["error"]["details"]


# =============================================================================
# Tests for GET /suppliers/{supplier_id}
# =============================================================================

def test_get_supplier_endpoint_routes_registered():
    """Verifies that both /suppliers/{supplier_id} and /api/v1/suppliers/{supplier_id} are registered."""
    route_map = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}
    assert "/suppliers/{supplier_id}" in route_map, "/suppliers/{supplier_id} is not registered"
    assert "GET" in route_map["/suppliers/{supplier_id}"]
    assert "/api/v1/suppliers/{supplier_id}" in route_map, "/api/v1/suppliers/{supplier_id} is not registered"
    assert "GET" in route_map["/api/v1/suppliers/{supplier_id}"]


def test_get_supplier_success(test_db_session):
    """Verifies complete, successful retrieval of a supplier by ID."""
    res = get_supplier(supplier_id=2, db=test_db_session)
    assert isinstance(res, SupplierDetailResponse)
    assert res.id == 2
    assert res.name == "Beta Latex Ltd"
    assert res.country == "India"
    assert res.region == "South Asia"
    assert res.capacity_per_month == 120.0
    assert res.base_risk == 35.0
    assert res.tier == 2


def test_get_supplier_aliases_retrieval_and_sorting(test_db_session):
    """Verifies aliases are retrieved from supplier_aliases and sorted alphabetically."""
    res = get_supplier(supplier_id=2, db=test_db_session)
    assert res.aliases == ["Beta Latex", "Beta Ltd"]

    # Supplier 1 has no aliases
    res1 = get_supplier(supplier_id=1, db=test_db_session)
    assert res1.aliases == []


def test_get_supplier_materials_and_qualification(test_db_session):
    """Verifies registered materials are retrieved with qualification status, sorted alphabetically."""
    res = get_supplier(supplier_id=2, db=test_db_session)
    assert len(res.materials) == 1
    mat = res.materials[0]
    assert isinstance(mat, SupplierDetailMaterial)
    assert mat.id == 1
    assert mat.name == "Natural Latex"
    assert mat.qualified is True


def test_get_supplier_upstream_and_downstream_relationships(test_db_session):
    """
    Verifies:
    - Downstream relationships in supplies_to (buyer id, buyer name, material)
    - Upstream relationships in supplied_by (supplier id, supplier name, material)
    """
    res = get_supplier(supplier_id=2, db=test_db_session)

    # Downstream: s2 supplies to s3 (Gamma Rubber) with Synthetic Rubber
    assert len(res.supplies_to) == 1
    downstream = res.supplies_to[0]
    assert isinstance(downstream, SupplierDetailSupplied)
    assert downstream.id == 3
    assert downstream.name == "Gamma Rubber"
    assert downstream.material == "Synthetic Rubber"

    # Upstream: s1 (Alpha Corp) supplies to s2 with Natural Latex
    assert len(res.supplied_by) == 1
    upstream = res.supplied_by[0]
    assert isinstance(upstream, SupplierDetailSupplied)
    assert upstream.id == 1
    assert upstream.name == "Alpha Corp"
    assert upstream.material == "Natural Latex"


def test_get_supplier_tier_calculation_and_null_tier(test_db_session):
    """
    Verifies:
    - Minimum non-null tier among active outgoing relationships is returned (s1: tier 1, s2: tier 2)
    - Null tier is returned when relationship tier is null (s3: tier None)
    """
    res1 = get_supplier(supplier_id=1, db=test_db_session)
    assert res1.tier == 1

    res2 = get_supplier(supplier_id=2, db=test_db_session)
    assert res2.tier == 2

    res3 = get_supplier(supplier_id=3, db=test_db_session)
    assert res3.tier is None


def test_get_supplier_not_found(test_db_session):
    """Verifies 404 NOT_FOUND response envelope when supplier ID does not exist."""
    res = get_supplier(supplier_id=999, db=test_db_session)
    assert res.status_code == 404

    body = json.loads(res.body.decode())
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Supplier 999 does not exist."
    assert body["error"]["details"] == {}


def test_get_supplier_inactive_returns_404(test_db_session):
    """Verifies 404 NOT_FOUND response envelope when supplier is inactive."""
    res = get_supplier(supplier_id=4, db=test_db_session)
    assert res.status_code == 404

    body = json.loads(res.body.decode())
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Supplier 4 does not exist."


def test_get_supplier_invalid_id_422(test_db_session):
    """Verifies 422 VALIDATION_ERROR response envelope when supplier ID is invalid (< 1)."""
    res = get_supplier(supplier_id=0, db=test_db_session)
    assert res.status_code == 422

    body = json.loads(res.body.decode())
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]


def test_get_supplier_openapi_contract():
    """Verifies OpenAPI schema documents /suppliers/{supplier_id} path parameter constraints."""
    schema = app.openapi()
    path_item = schema["paths"]["/suppliers/{supplier_id}"]["get"]
    param = path_item["parameters"][0]

    assert param["name"] == "supplier_id"
    assert param["in"] == "path"
    assert param["required"] is True
    assert param["schema"]["type"] == "integer"
    assert param["schema"]["minimum"] == 1
    assert "200" in path_item["responses"]
