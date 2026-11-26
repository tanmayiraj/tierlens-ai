"""
Isolated unit and integration tests for Risk Analysis API (TASK-017).
Conforms strictly to project-docs/API_SPEC.md Sections 4.6, 4.7, and 4.10.

Tests all seven endpoints following the established repository pattern:
1. POST /events (create_event)
2. GET /events (list_events)
3. GET /alerts (list_alerts)
4. GET /alerts/{id} (get_alert_detail)
5. PATCH /alerts/{id} (update_alert_status)
6. GET /impact/{event_id} (get_impact_analysis)
7. GET /risk/summary (get_risk_summary)

All tests execute with isolated temporary SQLite databases and direct router
handler invocations, completely avoiding TestClient ASGI thread contention.
"""

import json
import pytest
from datetime import date, datetime
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, init_db
from backend.models.db import (
    Supplier,
    Material,
    SupplierMaterial,
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
from backend.graph.service import GraphService, graph_service
from backend.api.risk import (
    create_event,
    list_events,
    list_alerts,
    get_alert_detail,
    update_alert_status,
    get_impact_analysis,
    get_risk_summary,
)
from backend.models.schemas import (
    EventCreateRequest,
    EventCreateResponse,
    EventListResponse,
    AlertListResponse,
    AlertDetailResponse,
    AlertUpdateStatusRequest,
    AlertUpdateStatusResponse,
    ImpactResponse,
    RiskSummaryResponse,
)


@pytest.fixture
def risk_api_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with the standard
    TierLens supply chain model for API endpoint verification.
    """
    db_file = tmp_path / "test_risk_api_isolated.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    init_db(target_engine=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    try:
        # 1. Suppliers
        s_mfg = Supplier(id=1, name="AutoMotive Corp", country="India", region="South Asia", is_active=True, base_risk=0.0, entity_type="manufacturer")
        s_tw = Supplier(id=2, name="TyreWorks Ltd", country="India", region="South Asia", is_active=True, base_risk=15.0, entity_type="supplier")
        s_gs = Supplier(id=3, name="GripSeal Components", country="India", region="South Asia", is_active=True, base_risk=10.0, entity_type="supplier")
        s_rc = Supplier(id=4, name="RubberCore Industries", country="India", region="South Asia", is_active=True, base_risk=25.0, entity_type="supplier")
        s_gl = Supplier(id=5, name="GreenLatex Pvt Ltd", country="India", region="South Asia", is_active=True, base_risk=35.0, entity_type="supplier")
        s_sa = Supplier(id=7, name="SouthAsia Latex Co", country="India", region="South Asia", is_active=True, base_risk=20.0, entity_type="supplier")

        session.add_all([s_mfg, s_tw, s_gs, s_rc, s_gl, s_sa])
        session.flush()

        # 2. Materials
        m_latex = Material(id=1, name="Natural Latex", material_type="raw", unit="MT")
        m_proc = Material(id=3, name="Processed Rubber", material_type="part", unit="MT")
        m_tyre = Material(id=4, name="Tyres", material_type="assembly", unit="units")
        m_seal = Material(id=5, name="Rubber Seals", material_type="part", unit="units")
        session.add_all([m_latex, m_proc, m_tyre, m_seal])
        session.flush()

        # 3. Capabilities (SupplierMaterial)
        sm_gl = SupplierMaterial(supplier_id=5, material_id=1, is_qualified=True)
        sm_sa = SupplierMaterial(supplier_id=7, material_id=1, is_qualified=True)
        session.add_all([sm_gl, sm_sa])
        session.flush()

        # 4. Plant, Product, Production Lines
        plant = Plant(id=1, manufacturer_id=1, name="Pune Assembly Plant", location="Pune, India")
        prod = Product(id=1, name="Sedan X", unit_revenue=1200000.0)
        session.add_all([plant, prod])
        session.flush()

        line_a = ProductionLine(id=1, plant_id=1, product_id=1, name="Line A", units_per_day=50.0, daily_revenue=60000000.0)
        line_b = ProductionLine(id=2, plant_id=1, product_id=1, name="Line B", units_per_day=30.0, daily_revenue=36000000.0)
        session.add_all([line_a, line_b])
        session.flush()

        # 5. Line Requirements
        lr_a = LineRequirement(line_id=1, material_id=4, qty_per_day=200.0, safety_stock_days=4)
        lr_b = LineRequirement(line_id=2, material_id=5, qty_per_day=120.0, safety_stock_days=5)
        session.add_all([lr_a, lr_b])
        session.flush()

        # 6. Approved Relationships
        # Rel 1: GreenLatex -> RubberCore (5 days)
        r1 = Relationship(id=1, supplier_id=5, buyer_id=4, material_id=1, inventory_days=5, lead_time_days=21, share_pct=70.0, status="approved")
        # Rel 3: RubberCore -> TyreWorks (4 days)
        r3 = Relationship(id=3, supplier_id=4, buyer_id=2, material_id=3, inventory_days=4, lead_time_days=10, share_pct=75.0, status="approved")
        # Rel 4: RubberCore -> GripSeal (6 days)
        r4 = Relationship(id=4, supplier_id=4, buyer_id=3, material_id=3, inventory_days=6, lead_time_days=10, share_pct=85.0, status="approved")
        # Rel 5: TyreWorks -> AutoMotive (feeds Line A)
        r5 = Relationship(id=5, supplier_id=2, buyer_id=1, material_id=4, inventory_days=3, lead_time_days=7, share_pct=100.0, status="approved")
        # Rel 6: GripSeal -> AutoMotive (feeds Line B)
        r6 = Relationship(id=6, supplier_id=3, buyer_id=1, material_id=5, inventory_days=4, lead_time_days=5, share_pct=100.0, status="approved")
        session.add_all([r1, r3, r4, r5, r6])
        session.flush()

        # 7. Document & Evidence
        doc = Document(id=1, filename="PO_1042.pdf", doc_type="purchase_order", file_path="data/sample_docs/PO_1042.pdf", extraction_status="done")
        session.add(doc)
        session.flush()

        ev = Evidence(id=1, document_id=1, page=1, snippet="PO_1042: GreenLatex supplies 40 MT Natural Latex", llm_confidence=0.95)
        session.add(ev)
        session.flush()

        re = RelationshipEvidence(relationship_id=1, evidence_id=1)
        session.add(re)
        session.commit()

        # Rebuild graph singleton with isolated session
        graph_service.rebuild(session)

        yield session
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# 1. Route Registration Checks
# =============================================================================

def test_risk_routes_registered():
    """
    Verifies that all seven risk endpoints are registered on both root and /api/v1 prefixes.
    """
    route_map = {}
    for r in app.routes:
        if hasattr(r, "methods"):
            route_map.setdefault(r.path, set()).update(r.methods)
    expected_endpoints = [
        ("/events", "POST"),
        ("/api/v1/events", "POST"),
        ("/events", "GET"),
        ("/api/v1/events", "GET"),
        ("/alerts", "GET"),
        ("/api/v1/alerts", "GET"),
        ("/alerts/{id}", "GET"),
        ("/api/v1/alerts/{id}", "GET"),
        ("/alerts/{id}", "PATCH"),
        ("/api/v1/alerts/{id}", "PATCH"),
        ("/impact/{event_id}", "GET"),
        ("/api/v1/impact/{event_id}", "GET"),
        ("/risk/summary", "GET"),
        ("/api/v1/risk/summary", "GET"),
    ]
    for path, method in expected_endpoints:
        assert path in route_map, f"Route {path} is not registered"
        assert method in route_map[path], f"Method {method} not allowed for {path}"


# =============================================================================
# 2. POST /events Tests
# =============================================================================

def test_create_event_endpoint_success(risk_api_db):
    """
    create_event logs disruption, evaluates risk, and persists Alert.
    """
    req = EventCreateRequest(
        supplier_id=5,
        event_type="shutdown",
        severity=5,
        start_date=date(2026, 11, 20),
        expected_duration_days=30,
        description="Factory closed after regional flooding in plantation district.",
        source="simulated",
        is_simulated=True,
    )

    res = create_event(payload=req, db=risk_api_db)
    assert isinstance(res, EventCreateResponse)
    assert res.event_id is not None
    assert res.alert_id is not None
    assert res.risk_score == 80.0
    assert res.severity_label == "critical"

    # Verify database persistence
    db_alert = risk_api_db.query(Alert).filter(Alert.id == res.alert_id).first()
    assert db_alert is not None
    assert db_alert.risk_score == 80.0
    assert db_alert.status == "open"
    assert db_alert.days_to_impact == 9
    assert db_alert.revenue_at_risk == 1944000000.0


def test_create_event_supplier_not_found(risk_api_db):
    """
    create_event with non-existent supplier returns 404 JSONResponse.
    """
    req = EventCreateRequest(
        supplier_id=99999,
        event_type="delay",
        severity=3,
        start_date=date(2026, 11, 20),
        expected_duration_days=10,
    )
    res = create_event(payload=req, db=risk_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404
    data = json.loads(res.body)
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 3. GET /events Tests
# =============================================================================

def test_list_events_endpoint(risk_api_db):
    """
    list_events returns paginated disruption events with supplier details and filtering.
    """
    ev1 = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=5, start_date=date(2026, 11, 20), expected_duration_days=30, is_simulated=True)
    ev2 = DisruptionEvent(supplier_id=2, event_type="delay", severity=2, start_date=date(2026, 11, 21), expected_duration_days=5, is_simulated=False)
    risk_api_db.add_all([ev1, ev2])
    risk_api_db.commit()

    # List all
    res = list_events(limit=50, offset=0, db=risk_api_db)
    assert isinstance(res, EventListResponse)
    assert res.total == 2
    assert len(res.items) == 2

    # Filter by supplier_id
    res_filt = list_events(supplier_id=5, limit=50, offset=0, db=risk_api_db)
    assert res_filt.total == 1
    assert res_filt.items[0].supplier.name == "GreenLatex Pvt Ltd"

    # Filter by is_simulated
    res_sim = list_events(is_simulated=False, limit=50, offset=0, db=risk_api_db)
    assert res_sim.total == 1
    assert res_sim.items[0].event_type == "delay"


# =============================================================================
# 4. GET /alerts Tests
# =============================================================================

def test_list_alerts_endpoint(risk_api_db):
    """
    list_alerts returns alerts with status/severity filtering and risk_score sorting.
    """
    ev = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=5, start_date=date(2026, 11, 20), is_simulated=True)
    risk_api_db.add(ev)
    risk_api_db.flush()

    a1 = Alert(event_id=ev.id, severity_label="critical", risk_score=80.0, score_breakdown={}, days_to_impact=9, revenue_at_risk=1944000000.0, status="open")
    a2 = Alert(event_id=ev.id, severity_label="low", risk_score=25.0, score_breakdown={}, days_to_impact=None, revenue_at_risk=0.0, status="resolved")
    risk_api_db.add_all([a1, a2])
    risk_api_db.commit()

    # Default list sorted by risk_score:desc
    res = list_alerts(sort="risk_score:desc", limit=50, offset=0, db=risk_api_db)
    assert isinstance(res, AlertListResponse)
    assert res.total == 2
    assert res.items[0].risk_score == 80.0
    assert res.items[1].risk_score == 25.0

    # Filter by status
    res_open = list_alerts(status="open", limit=50, offset=0, db=risk_api_db)
    assert res_open.total == 1
    assert res_open.items[0].status == "open"

    # Filter by severity
    res_crit = list_alerts(severity_label="critical", limit=50, offset=0, db=risk_api_db)
    assert res_crit.total == 1
    assert res_crit.items[0].severity_label == "critical"


# =============================================================================
# 5. GET /alerts/{id} Tests
# =============================================================================

def test_get_alert_detail_endpoint(risk_api_db):
    """
    get_alert_detail returns score breakdown, affected nodes, and linked evidence.
    """
    ev = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=5, start_date=date(2026, 11, 20), expected_duration_days=30, is_simulated=True)
    risk_api_db.add(ev)
    risk_api_db.flush()

    alert = Alert(
        event_id=ev.id,
        severity_label="critical",
        risk_score=80.0,
        score_breakdown={
            "event_severity": 24.0,
            "criticality": 22.0,
            "single_source_exposure": 20.0,
            "buffer_gap": 10.5,
            "regional_risk": 3.5,
            "total": 80.0,
        },
        days_to_impact=9,
        revenue_at_risk=1944000000.0,
        explanation="GreenLatex disruption impacts Line A and Line B.",
        status="open",
    )
    risk_api_db.add(alert)
    risk_api_db.flush()

    an1 = AlertAffectedNode(alert_id=alert.id, node_type="supplier", node_id=4, path_depth=1, days_to_impact=5)
    an2 = AlertAffectedNode(alert_id=alert.id, node_type="line", node_id=1, path_depth=3, days_to_impact=9)
    risk_api_db.add_all([an1, an2])
    risk_api_db.commit()

    res = get_alert_detail(id=alert.id, db=risk_api_db)
    assert isinstance(res, AlertDetailResponse)
    assert res.id == alert.id
    assert res.risk_score == 80.0
    assert res.severity_label == "critical"
    assert res.score_breakdown["event_severity"] == 24.0
    assert res.event.supplier == "GreenLatex Pvt Ltd"
    assert len(res.affected) == 2
    assert len(res.evidence) >= 1
    assert res.evidence[0].document == "PO_1042.pdf"
    assert res.alternatives_url == "/api/v1/alternatives/5"


def test_get_alert_detail_not_found(risk_api_db):
    """
    get_alert_detail with unknown ID returns 404 JSONResponse.
    """
    res = get_alert_detail(id=99999, db=risk_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404
    data = json.loads(res.body)
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 6. PATCH /alerts/{id} Tests
# =============================================================================

def test_update_alert_status_to_investigating(risk_api_db):
    """
    Validates specifically transitioning an alert from open to investigating.
    """
    ev = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=4, start_date=date(2026, 11, 20), is_simulated=True)
    risk_api_db.add(ev)
    risk_api_db.flush()

    alert = Alert(event_id=ev.id, severity_label="high", risk_score=65.0, score_breakdown={}, status="open")
    risk_api_db.add(alert)
    risk_api_db.commit()

    res = update_alert_status(payload=AlertUpdateStatusRequest(status="investigating"), id=alert.id, db=risk_api_db)
    assert isinstance(res, AlertUpdateStatusResponse)
    assert res.id == alert.id
    assert res.status == "investigating"

    risk_api_db.refresh(alert)
    assert alert.status == "investigating"


def test_update_alert_status_endpoint(risk_api_db):
    """
    update_alert_status transitions lifecycle status across all four approved states:
    open -> investigating -> acknowledged -> resolved.
    """
    ev = DisruptionEvent(supplier_id=5, event_type="delay", severity=2, start_date=date(2026, 11, 20), is_simulated=True)
    risk_api_db.add(ev)
    risk_api_db.flush()

    alert = Alert(event_id=ev.id, severity_label="low", risk_score=20.0, score_breakdown={}, status="open")
    risk_api_db.add(alert)
    risk_api_db.commit()

    # 1. Transition to investigating
    res_inv = update_alert_status(payload=AlertUpdateStatusRequest(status="investigating"), id=alert.id, db=risk_api_db)
    assert isinstance(res_inv, AlertUpdateStatusResponse)
    assert res_inv.status == "investigating"

    # 2. Transition to acknowledged
    res_ack = update_alert_status(payload=AlertUpdateStatusRequest(status="acknowledged"), id=alert.id, db=risk_api_db)
    assert isinstance(res_ack, AlertUpdateStatusResponse)
    assert res_ack.status == "acknowledged"

    # 3. Transition to resolved
    res_res = update_alert_status(payload=AlertUpdateStatusRequest(status="resolved"), id=alert.id, db=risk_api_db)
    assert isinstance(res_res, AlertUpdateStatusResponse)
    assert res_res.status == "resolved"

    risk_api_db.refresh(alert)
    assert alert.status == "resolved"


def test_update_alert_status_not_found(risk_api_db):
    """
    update_alert_status with unknown ID returns 404 JSONResponse.
    """
    res = update_alert_status(payload=AlertUpdateStatusRequest(status="acknowledged"), id=99999, db=risk_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404
    data = json.loads(res.body)
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 7. GET /impact/{event_id} Tests
# =============================================================================

def test_get_impact_analysis_endpoint(risk_api_db):
    """
    get_impact_analysis returns downstream graph traversal, path reconstructions,
    and revenue exposure.
    """
    ev = DisruptionEvent(
        supplier_id=5,
        event_type="shutdown",
        severity=5,
        expected_duration_days=30,
        start_date=date(2026, 11, 20),
        is_simulated=True,
    )
    risk_api_db.add(ev)
    risk_api_db.commit()

    res = get_impact_analysis(event_id=ev.id, db=risk_api_db)
    assert isinstance(res, ImpactResponse)
    assert res.event_id == ev.id
    assert res.origin.label == "GreenLatex Pvt Ltd"
    assert res.origin.tier == 3

    # Summary
    assert res.summary.suppliers_affected == 3  # RubberCore, TyreWorks, GripSeal
    assert res.summary.lines_affected == 2      # Line A, Line B
    assert res.summary.first_impact_in_days == 9
    assert res.summary.revenue_at_risk == 1944000000.0

    # Paths
    assert len(res.paths) >= 2
    path_nodes = [p.nodes for p in res.paths]
    assert any("Line A" in p for p in path_nodes)
    assert any("Line B" in p for p in path_nodes)

    # Affected nodes list
    node_names = {n.name for n in res.affected_nodes}
    assert "RubberCore Industries" in node_names
    assert "TyreWorks Ltd" in node_names
    assert "Line A" in node_names
    assert "Line B" in node_names


def test_get_impact_analysis_not_found(risk_api_db):
    """
    get_impact_analysis with unknown event_id returns 404 JSONResponse.
    """
    res = get_impact_analysis(event_id=99999, db=risk_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404
    data = json.loads(res.body)
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 8. GET /risk/summary Tests
# =============================================================================

def test_get_risk_summary_endpoint(risk_api_db):
    """
    get_risk_summary returns network tier counts, open alert breakdowns,
    top risky suppliers, and total revenue at risk.
    """
    ev = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=5, expected_duration_days=30, start_date=date(2026, 11, 20), is_simulated=True)
    risk_api_db.add(ev)
    risk_api_db.flush()

    alert = Alert(
        event_id=ev.id,
        severity_label="critical",
        risk_score=80.0,
        score_breakdown={},
        revenue_at_risk=1944000000.0,
        status="open",
    )
    risk_api_db.add(alert)
    risk_api_db.commit()

    res = get_risk_summary(db=risk_api_db)
    assert isinstance(res, RiskSummaryResponse)

    # Network counts
    assert res.network.suppliers >= 5
    assert res.network.tier1 >= 2
    assert res.network.tier2 >= 1
    assert res.network.tier3 >= 1

    # Open Alerts counts
    assert res.open_alerts.critical >= 1
    assert res.total_revenue_at_risk >= 1944000000.0

    # Top risky suppliers
    assert len(res.top_risky_suppliers) > 0
    assert res.top_risky_suppliers[0].name == "GreenLatex Pvt Ltd"
    assert res.top_risky_suppliers[0].risk_score == 80.0
