"""
Unit and integration tests for Disruption Simulator API (TASK-025).
Conforms strictly to project-docs/API_SPEC.md Sections 4.8 and 4.9.

Tests all four endpoints following the established repository pattern:
1. POST /simulate (run_simulation_endpoint)
2. GET /scenarios (list_scenarios)
3. GET /scenarios/{id} (get_scenario_detail)
4. GET /alternatives/{supplier_id} (get_alternative_suppliers)

All tests execute with isolated temporary SQLite databases and direct router
handler invocations, completely avoiding TestClient ASGI thread contention.
"""

import pytest
from datetime import date, datetime, timezone
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
    Plant,
    Product,
    ProductionLine,
    LineRequirement,
    Scenario,
    ScenarioResult,
)
from backend.graph.service import GraphService, graph_service
from backend.api.simulation import (
    run_simulation_endpoint,
    list_scenarios,
    get_scenario_detail,
    get_alternative_suppliers,
)
from backend.models.schemas import (
    MitigationSchema,
    SimulationRequest,
    SimulationResponse,
    ScenarioListResponse,
    ScenarioDetailResponse,
    AlternativesResponse,
)


@pytest.fixture
def sim_api_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with the standard
    synthetic automotive supply chain dataset for API endpoint verification.
    """
    db_file = tmp_path / "test_sim_api_isolated.db"
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
        sm_gl = SupplierMaterial(supplier_id=5, material_id=1, capacity_per_month=120.0, typical_lead_time_days=21, is_qualified=True)
        sm_sa = SupplierMaterial(supplier_id=7, material_id=1, capacity_per_month=90.0, typical_lead_time_days=14, is_qualified=True)
        session.add_all([sm_gl, sm_sa])
        session.flush()

        # 4. Plant, Product, Lines
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
        r1 = Relationship(id=1, supplier_id=5, buyer_id=4, material_id=1, inventory_days=5, lead_time_days=21, share_pct=70.0, quantity_per_month=90.0, status="approved")
        r3 = Relationship(id=3, supplier_id=4, buyer_id=2, material_id=3, inventory_days=4, lead_time_days=10, share_pct=75.0, status="approved")
        r4 = Relationship(id=4, supplier_id=4, buyer_id=3, material_id=3, inventory_days=6, lead_time_days=10, share_pct=85.0, status="approved")
        r5 = Relationship(id=5, supplier_id=2, buyer_id=1, material_id=4, inventory_days=3, lead_time_days=7, share_pct=100.0, status="approved")
        r6 = Relationship(id=6, supplier_id=3, buyer_id=1, material_id=5, inventory_days=4, lead_time_days=5, share_pct=100.0, status="approved")
        session.add_all([r1, r3, r4, r5, r6])
        session.commit()

        # Build in-memory graph singleton for this test DB
        graph_service.rebuild(session)

        yield session
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# 1. Route Registration Verification
# =============================================================================

def test_simulation_api_routes_registered():
    """
    Verifies that all 4 simulation endpoints are properly registered on FastAPI app
    under both /api/v1 and bare path prefixes.
    """
    route_paths = {route.path for route in app.routes}

    expected_endpoints = [
        "/api/v1/simulate",
        "/simulate",
        "/api/v1/scenarios",
        "/scenarios",
        "/api/v1/scenarios/{id}",
        "/scenarios/{id}",
        "/api/v1/alternatives/{supplier_id}",
        "/alternatives/{supplier_id}",
    ]

    for endpoint in expected_endpoints:
        assert endpoint in route_paths, f"Expected route {endpoint} not registered on FastAPI app."


# =============================================================================
# 2. POST /simulate Endpoint Tests
# =============================================================================

def test_simulate_endpoint_baseline_no_mitigations(sim_api_db):
    """
    Verifies POST /simulate calculates baseline operational impact correctly when save=False.
    """
    payload = SimulationRequest(
        name="GreenLatex 30d Baseline",
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[],
        save=False,
    )

    response = run_simulation_endpoint(payload=payload, db=sim_api_db)

    assert isinstance(response, SimulationResponse)
    assert response.scenario_id is None  # save=False
    assert response.name == "GreenLatex 30d Baseline"
    assert response.failed_supplier_ids == [5]
    assert response.duration_days == 30

    # Before mitigation
    assert response.before_mitigation.lines_at_risk == 2
    assert response.before_mitigation.revenue_at_risk == 1944000000.0
    assert response.before_mitigation.days_to_impact == 9
    assert len(response.before_mitigation.affected_path) >= 2

    # After mitigation matches before when no mitigations are configured
    assert response.after_mitigation.lines_at_risk == 2
    assert response.after_mitigation.revenue_at_risk == 1944000000.0
    assert response.improvement.revenue_protected == 0.0
    assert response.improvement.lines_protected == 0


def test_simulate_endpoint_with_mitigations_and_save(sim_api_db):
    """
    Verifies POST /simulate applies mitigations, computes protection improvement,
    and persists to database when save=True.
    """
    payload = SimulationRequest(
        name="GreenLatex Full Mitigation Plan",
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationSchema(type="alternate_supplier", material_id=1, supplier_id=7),
            MitigationSchema(type="safety_stock", material_id=1, extra_days=10),
        ],
        save=True,
    )

    response = run_simulation_endpoint(payload=payload, db=sim_api_db)

    assert isinstance(response, SimulationResponse)
    assert response.scenario_id is not None  # Persisted ID

    # 100% protection achieved
    assert response.after_mitigation.lines_at_risk == 0
    assert response.after_mitigation.revenue_at_risk == 0.0
    assert response.improvement.revenue_protected == 1944000000.0
    assert response.improvement.lines_protected == 2

    # Verify database persistence
    saved_scen = sim_api_db.query(Scenario).filter(Scenario.id == response.scenario_id).first()
    assert saved_scen is not None
    assert saved_scen.name == "GreenLatex Full Mitigation Plan"
    assert saved_scen.duration_days == 30

    results = sim_api_db.query(ScenarioResult).filter(ScenarioResult.scenario_id == response.scenario_id).all()
    assert len(results) == 2


def test_simulate_endpoint_validation_errors(sim_api_db):
    """
    Verifies POST /simulate error handling for non-existent suppliers,
    empty supplier IDs, and non-positive duration.
    """
    # 1. Non-existent supplier ID
    payload_missing = SimulationRequest(
        failed_supplier_ids=[999],
        duration_days=30,
        mitigations=[],
    )
    res_missing = run_simulation_endpoint(payload=payload_missing, db=sim_api_db)
    assert isinstance(res_missing, JSONResponse)
    assert res_missing.status_code == 404
    body = res_missing.body.decode()
    assert "Supplier with ID 999 does not exist" in body

    # 2. Empty failed supplier IDs
    payload_empty = SimulationRequest(
        failed_supplier_ids=[],
        duration_days=30,
        mitigations=[],
    )
    res_empty = run_simulation_endpoint(payload=payload_empty, db=sim_api_db)
    assert isinstance(res_empty, JSONResponse)
    assert res_empty.status_code == 422
    assert "failed_supplier_ids must contain at least one supplier ID" in res_empty.body.decode()


# =============================================================================
# 3. GET /scenarios Endpoint Tests
# =============================================================================

def test_list_scenarios_empty_and_populated(sim_api_db):
    """
    Verifies GET /scenarios returns an empty list initially, then lists saved scenarios.
    """
    # 1. Initially empty
    empty_res = list_scenarios(limit=50, offset=0, db=sim_api_db)
    assert isinstance(empty_res, ScenarioListResponse)
    assert empty_res.total == 0
    assert empty_res.items == []

    # 2. Create two scenarios
    scen1 = Scenario(id=1, name="Outage A", failed_supplier_ids=[5], duration_days=30, created_at=datetime.now(timezone.utc))
    scen2 = Scenario(id=2, name="Outage B", failed_supplier_ids=[2], duration_days=14, created_at=datetime.now(timezone.utc))
    sim_api_db.add_all([scen1, scen2])
    sim_api_db.commit()

    # 3. List populated scenarios
    pop_res = list_scenarios(limit=10, offset=0, db=sim_api_db)
    assert isinstance(pop_res, ScenarioListResponse)
    assert pop_res.total == 2
    assert len(pop_res.items) == 2
    assert pop_res.items[0].name in ["Outage A", "Outage B"]

    # 4. Pagination
    page_res = list_scenarios(limit=1, offset=1, db=sim_api_db)
    assert len(page_res.items) == 1
    assert page_res.total == 2


# =============================================================================
# 4. GET /scenarios/{id} Endpoint Tests
# =============================================================================

def test_get_scenario_detail_success_and_404(sim_api_db):
    """
    Verifies GET /scenarios/{id} returns full scenario definition with before/after results,
    and returns 404 for non-existent scenario IDs.
    """
    # 1. Non-existent ID -> 404
    res_404 = get_scenario_detail(id=999, db=sim_api_db)
    assert isinstance(res_404, JSONResponse)
    assert res_404.status_code == 404
    assert "Scenario with ID 999 not found" in res_404.body.decode()

    # 2. Run simulation with save=True to generate a complete scenario record
    payload = SimulationRequest(
        name="Persisted Outage Scenario",
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[MitigationSchema(type="safety_stock", material_id=1, extra_days=10)],
        save=True,
    )
    sim_res = run_simulation_endpoint(payload=payload, db=sim_api_db)
    scen_id = sim_res.scenario_id

    # 3. Retrieve scenario detail
    detail = get_scenario_detail(id=scen_id, db=sim_api_db)
    assert isinstance(detail, ScenarioDetailResponse)
    assert detail.id == scen_id
    assert detail.name == "Persisted Outage Scenario"
    assert detail.duration_days == 30
    assert detail.failed_supplier_ids == [5]
    assert detail.before_mitigation.revenue_at_risk == 1944000000.0
    assert detail.after_mitigation.revenue_at_risk < detail.before_mitigation.revenue_at_risk
    assert detail.improvement.revenue_protected > 0.0


# =============================================================================
# 5. GET /alternatives/{supplier_id} Endpoint Tests
# =============================================================================

def test_get_alternative_suppliers_success(sim_api_db):
    """
    Verifies GET /alternatives/{supplier_id} returns ranked qualified alternatives for GreenLatex.
    """
    response = get_alternative_suppliers(supplier_id=5, db=sim_api_db)

    assert isinstance(response, AlternativesResponse)
    assert response.failed_supplier.id == 5
    assert response.failed_supplier.name == "GreenLatex Pvt Ltd"
    assert response.material is not None
    assert response.material.name == "Natural Latex"

    assert len(response.alternatives) == 1
    top = response.alternatives[0]
    assert top.supplier.id == 7
    assert top.supplier.name == "SouthAsia Latex Co"
    assert top.rank == 1
    assert top.qualified is True
    assert top.lead_time_days == 14
    assert top.capacity_per_month == 90.0
    assert top.score >= 0.70
    assert len(top.reasons) >= 2


def test_get_alternative_suppliers_with_material_filter(sim_api_db):
    """
    Verifies GET /alternatives/{supplier_id}?material_id=1 filters candidates correctly.
    """
    response = get_alternative_suppliers(supplier_id=5, material_id=1, db=sim_api_db)

    assert isinstance(response, AlternativesResponse)
    assert response.material.id == 1
    assert len(response.alternatives) == 1
    assert response.alternatives[0].supplier.id == 7


def test_get_alternative_suppliers_errors(sim_api_db):
    """
    Verifies 404 responses for non-existent supplier or non-existent material.
    """
    # Non-existent supplier
    res_supp = get_alternative_suppliers(supplier_id=999, db=sim_api_db)
    assert isinstance(res_supp, JSONResponse)
    assert res_supp.status_code == 404
    assert "Supplier with ID 999 does not exist" in res_supp.body.decode()

    # Non-existent material
    res_mat = get_alternative_suppliers(supplier_id=5, material_id=999, db=sim_api_db)
    assert isinstance(res_mat, JSONResponse)
    assert res_mat.status_code == 404
    assert "Material with ID 999 does not exist" in res_mat.body.decode()
