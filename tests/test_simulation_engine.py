"""
Unit and integration tests for the Disruption Simulation Engine (TASK-025).
Validates:
- Baseline disruption impact propagation and line downtime calculation.
- Alternate supplier mitigation and lead-time gap dynamics.
- Safety stock buffer expansion.
- Combined mitigation eliminating 100% of revenue exposure.
- Expedited logistics and rerouting mitigation levers.
- Capacity constraints and capacity-adjusted deficit calculations.
- Qualified alternative supplier ranking and recommendation logic.
- Complete isolation: live graph service is never mutated.
- Proper error handling for invalid inputs and edge cases.
- Persistence to scenarios and scenario_results when save=True.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, init_db
from backend.models.db import (
    Supplier,
    Material,
    Relationship,
    Plant,
    Product,
    ProductionLine,
    LineRequirement,
    SupplierMaterial,
    Scenario,
    ScenarioResult,
)
from backend.graph.service import GraphService
from backend.services.simulation_engine import (
    SimulationEngine,
    MitigationInput,
    SimulationResult,
)


@pytest.fixture
def sim_test_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with the
    standard synthetic automotive supply chain dataset.
    """
    db_file = tmp_path / "test_sim_isolated.db"
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
        # GreenLatex: capacity 120/mo, typical lead time 21 days
        sm_gl = SupplierMaterial(supplier_id=5, material_id=1, capacity_per_month=120.0, typical_lead_time_days=21, is_qualified=True)
        # SouthAsia Latex: capacity 90/mo, typical lead time 14 days (alternate)
        sm_sa = SupplierMaterial(supplier_id=7, material_id=1, capacity_per_month=90.0, typical_lead_time_days=14, is_qualified=True)
        session.add_all([sm_gl, sm_sa])
        session.flush()

        # 4. Plant, Product, Lines
        plant = Plant(id=1, manufacturer_id=1, name="Pune Assembly Plant", location="Pune, Maharashtra, India")
        prod = Product(id=1, name="Sedan X", unit_revenue=1200000.0)
        session.add_all([plant, prod])
        session.flush()

        # Line A: 60,000,000 INR/day (₹6 Cr/day)
        line_a = ProductionLine(id=1, plant_id=1, product_id=1, name="Line A", units_per_day=50.0, daily_revenue=60000000.0)
        # Line B: 36,000,000 INR/day (₹3.6 Cr/day)
        line_b = ProductionLine(id=2, plant_id=1, product_id=1, name="Line B", units_per_day=30.0, daily_revenue=36000000.0)
        session.add_all([line_a, line_b])
        session.flush()

        # 5. Line Requirements
        lr_a = LineRequirement(line_id=1, material_id=4, qty_per_day=200.0, safety_stock_days=4)
        lr_b = LineRequirement(line_id=2, material_id=5, qty_per_day=120.0, safety_stock_days=5)
        session.add_all([lr_a, lr_b])
        session.flush()

        # 6. Approved Relationships with exact inventory buffers
        # Rel 1: GreenLatex -> RubberCore (inventory_days = 5)
        r1 = Relationship(id=1, supplier_id=5, buyer_id=4, material_id=1, inventory_days=5, lead_time_days=21, share_pct=70.0, quantity_per_month=90.0, status="approved")
        # Rel 3: RubberCore -> TyreWorks (inventory_days = 4)
        r3 = Relationship(id=3, supplier_id=4, buyer_id=2, material_id=3, inventory_days=4, lead_time_days=10, share_pct=75.0, status="approved")
        # Rel 4: RubberCore -> GripSeal (inventory_days = 6)
        r4 = Relationship(id=4, supplier_id=4, buyer_id=3, material_id=3, inventory_days=6, lead_time_days=10, share_pct=85.0, status="approved")
        # Rel 5: TyreWorks -> AutoMotive (Line A delivery)
        r5 = Relationship(id=5, supplier_id=2, buyer_id=1, material_id=4, inventory_days=3, lead_time_days=7, share_pct=100.0, status="approved")
        # Rel 6: GripSeal -> AutoMotive (Line B delivery)
        r6 = Relationship(id=6, supplier_id=3, buyer_id=1, material_id=5, inventory_days=4, lead_time_days=5, share_pct=100.0, status="approved")

        session.add_all([r1, r3, r4, r5, r6])
        session.commit()

        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def isolated_graph_service(sim_test_db):
    """Provides a fresh, isolated GraphService instance built from the test database."""
    gs = GraphService()
    gs.rebuild(sim_test_db)
    return gs


# =============================================================================
# Unit Tests
# =============================================================================

def test_simulation_baseline_without_mitigations(sim_test_db, isolated_graph_service):
    """
    Verifies that running a simulation without mitigations calculates the exact
    unbuffered downtime and revenue at risk for GreenLatex (30 days outage).
    Line A: 9d buffer -> 21 unbuffered days * 60,000,000 = 1,260,000,000
    Line B: 11d buffer -> 19 unbuffered days * 36,000,000 = 684,000,000
    Total Revenue at Risk = 1,944,000,000 INR
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],  # GreenLatex
        duration_days=30,
        mitigations=[],
        scenario_name="GreenLatex 30-day baseline",
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Before mitigation assertions
    assert result.before_mitigation.lines_at_risk == 2
    assert result.before_mitigation.revenue_at_risk == 1944000000.0
    assert result.before_mitigation.days_to_impact == 9
    assert result.before_mitigation.affected_path == [
        "GreenLatex Pvt Ltd",
        "RubberCore Industries",
        "TyreWorks Ltd",
        "Line A",
    ]

    # After mitigation should match before when no mitigations are configured
    assert result.after_mitigation.lines_at_risk == 2
    assert result.after_mitigation.revenue_at_risk == 1944000000.0
    assert result.after_mitigation.days_to_impact == 9

    # Improvement metrics
    assert result.improvement.revenue_protected == 0.0
    assert result.improvement.lines_protected == 0
    assert any("Baseline simulation completed" in n for n in result.notes)


def test_simulation_with_alternate_supplier_mitigation(sim_test_db, isolated_graph_service):
    """
    Verifies that engaging an alternate supplier (SouthAsia Latex Co, 14 days lead)
    shortens the unbuffered window to the lead-time arrival gap (14 - 9 = 5 days for Line A,
    14 - 11 = 3 days for Line B).
    """
    engine = SimulationEngine()
    mitigations = [
        MitigationInput(
            type="alternate_supplier",
            material_id=1,  # Natural Latex
            supplier_id=7,  # SouthAsia Latex Co
            share_pct=100.0,
        )
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Line A downtime reduced to gap: 14 - 9 = 5 days -> 5 * 60M = 300,000,000
    # Line B downtime reduced to gap: 14 - 11 = 3 days -> 3 * 36M = 108,000,000
    # New Revenue at Risk = 408,000,000 INR
    assert result.after_mitigation.lines_at_risk == 2
    assert result.after_mitigation.revenue_at_risk < result.before_mitigation.revenue_at_risk
    assert result.after_mitigation.revenue_at_risk == pytest.approx(408000000.0, rel=1e-3)

    # Improvement
    assert result.improvement.revenue_protected == pytest.approx(1536000000.0, rel=1e-3)
    assert any("Engaged alternate supplier SouthAsia Latex Co" in n for n in result.notes)


def test_simulation_with_safety_stock_mitigation(sim_test_db, isolated_graph_service):
    """
    Verifies adding 10 days of safety stock increases the buffer, reducing unbuffered downtime.
    Line A buffer increases from 9 to 19 days -> 11 unbuffered days.
    Line B buffer increases from 11 to 21 days -> 9 unbuffered days.
    """
    engine = SimulationEngine()
    mitigations = [
        MitigationInput(
            type="safety_stock",
            material_id=1,
            extra_days=10,
        )
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Line A: 11 days * 60M = 660,000,000
    # Line B: 9 days * 36M = 324,000,000
    # Expected after: 984,000,000 INR
    assert result.after_mitigation.revenue_at_risk == pytest.approx(984000000.0, rel=1e-3)
    assert result.improvement.revenue_protected == pytest.approx(960000000.0, rel=1e-3)
    assert result.after_mitigation.days_to_impact == 19


def test_simulation_combined_alternate_and_safety_stock_eliminates_all_downtime(sim_test_db, isolated_graph_service):
    """
    Verifies that combining an alternate supplier (14 days lead) with 10 days of safety stock
    bridges the lead-time gap completely (19-day buffer > 14-day lead time).
    Result: 0 lines at risk, 0 revenue at risk, 100% revenue protected.
    """
    engine = SimulationEngine()
    mitigations = [
        MitigationInput(
            type="alternate_supplier",
            material_id=1,
            supplier_id=7,  # SouthAsia Latex Co (lead time 14 days)
        ),
        MitigationInput(
            type="safety_stock",
            material_id=1,
            extra_days=10,  # Buffer increases from 9 to 19 days
        ),
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        scenario_name="GreenLatex Full Mitigation Plan",
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # 100% protection achieved
    assert result.after_mitigation.lines_at_risk == 0
    assert result.after_mitigation.revenue_at_risk == 0.0
    assert result.after_mitigation.days_to_impact is None
    assert result.after_mitigation.affected_path == []

    # Improvement: full baseline exposure protected
    assert result.improvement.revenue_protected == 1944000000.0
    assert result.improvement.lines_protected == 2
    assert any("Full disruption protection achieved" in n for n in result.notes)


def test_simulation_expedite_mitigation(sim_test_db, isolated_graph_service):
    """
    Verifies that expediting logistics reduces lead time, shortening the disruption gap.
    Alternate supplier lead time (14 days) reduced by 5 days -> 9 days.
    Matches Line A's 9-day buffer exactly -> 0 gap!
    """
    engine = SimulationEngine()
    mitigations = [
        MitigationInput(
            type="expedite",
            supplier_id=7,
            lead_time_reduction_days=5,
        ),
        MitigationInput(
            type="alternate_supplier",
            material_id=1,
            supplier_id=7,
        ),
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Expedited lead time is 9 days, which matches Line A buffer (9d) and is earlier than Line B (11d)
    assert result.after_mitigation.lines_at_risk == 0
    assert result.after_mitigation.revenue_at_risk == 0.0
    assert any("Expedited logistics" in n for n in result.notes)


def test_simulation_reroute_mitigation(sim_test_db, isolated_graph_service):
    """
    Verifies that reroute mitigation applies a standard transition lead time and reduces exposure.
    """
    engine = SimulationEngine()
    mitigations = [
        MitigationInput(
            type="reroute",
            from_supplier_id=7,
            to_supplier_id=4,
            material_id=1,
        )
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Rerouting engages the alternate path with 7-day lead time
    assert result.after_mitigation.revenue_at_risk < result.before_mitigation.revenue_at_risk
    assert any("Rerouted Natural Latex" in n for n in result.notes)


def test_simulation_capacity_constrained_alternate_supplier(sim_test_db, isolated_graph_service):
    """
    Verifies that an alternate supplier with limited capacity coverage models the remaining
    capacity deficit correctly after arrival.
    """
    engine = SimulationEngine()
    # Share pct limited to 50%
    mitigations = [
        MitigationInput(
            type="alternate_supplier",
            material_id=1,
            supplier_id=7,
            share_pct=50.0,
        )
    ]

    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=mitigations,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Revenue at risk is reduced, but non-zero due to 50% capacity deficit
    assert 0.0 < result.after_mitigation.revenue_at_risk < result.before_mitigation.revenue_at_risk


def test_simulation_disruption_absorbed_by_buffer(sim_test_db, isolated_graph_service):
    """
    Verifies that when a disruption's duration (5 days) is shorter than the cumulative buffer (9 days),
    revenue at risk is strictly 0.0 and days_to_impact is None.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=5,  # Less than 9-day buffer
        mitigations=[],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert result.before_mitigation.lines_at_risk == 0
    assert result.before_mitigation.revenue_at_risk == 0.0
    assert result.before_mitigation.days_to_impact is None
    assert result.after_mitigation.lines_at_risk == 0


def test_simulation_live_graph_never_mutated(sim_test_db, isolated_graph_service):
    """
    Guarantees that GraphService in-memory graph is never mutated during a simulation.
    Checks node count, edge count, and edge data before and after.
    """
    nodes_before = isolated_graph_service.node_count
    edges_before = isolated_graph_service.edge_count
    edges_data_before = list(isolated_graph_service.get_graph_copy().edges(data=True))

    engine = SimulationEngine()
    engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(type="alternate_supplier", material_id=1, supplier_id=7),
            MitigationInput(type="safety_stock", material_id=1, extra_days=10),
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert isolated_graph_service.node_count == nodes_before
    assert isolated_graph_service.edge_count == edges_before
    edges_data_after = list(isolated_graph_service.get_graph_copy().edges(data=True))
    assert edges_data_before == edges_data_after


def test_simulation_input_validation(sim_test_db, isolated_graph_service):
    """
    Verifies that the simulation engine rejects invalid inputs with descriptive ValueErrors.
    """
    engine = SimulationEngine()

    # Empty failed supplier IDs
    with pytest.raises(ValueError, match="failed_supplier_ids must contain at least one supplier ID"):
        engine.run_simulation([], 30, db=sim_test_db, graph_service=isolated_graph_service)

    # Zero or negative duration
    with pytest.raises(ValueError, match="duration_days must be a positive integer"):
        engine.run_simulation([5], 0, db=sim_test_db, graph_service=isolated_graph_service)

    # Non-existent supplier
    with pytest.raises(ValueError, match="Supplier with ID 999 does not exist"):
        engine.run_simulation([999], 30, db=sim_test_db, graph_service=isolated_graph_service)

    # Failed supplier used as alternate
    with pytest.raises(ValueError, match="is disrupted and cannot serve as an alternate"):
        engine.run_simulation(
            [5],
            30,
            mitigations=[MitigationInput(type="alternate_supplier", material_id=1, supplier_id=5)],
            db=sim_test_db,
            graph_service=isolated_graph_service,
        )

    # Missing material_id in safety stock
    with pytest.raises(ValueError, match="safety_stock mitigation requires 'material_id'"):
        engine.run_simulation(
            [5],
            30,
            mitigations=[MitigationInput(type="safety_stock", extra_days=10)],
            db=sim_test_db,
            graph_service=isolated_graph_service,
        )


def test_recommend_alternatives_for_greenlatex(sim_test_db):
    """
    Verifies that recommend_alternatives identifies SouthAsia Latex Co as the
    qualified alternative for GreenLatex Pvt Ltd, ranked by multi-criteria score.
    """
    engine = SimulationEngine()
    recs = engine.recommend_alternatives(
        supplier_id=5,  # GreenLatex
        material_id=1,  # Natural Latex
        db=sim_test_db,
    )

    assert len(recs) == 1
    top = recs[0]
    assert top.supplier_id == 7
    assert top.supplier_name == "SouthAsia Latex Co"
    assert top.rank == 1
    assert top.qualified is True
    assert top.lead_time_days == 14
    assert top.capacity_per_month == 90.0
    assert top.region_risk == "low"
    assert top.score >= 0.70
    assert any("Qualified for Natural Latex" in r for r in top.reasons)
    assert any("Shorter lead time" in r for r in top.reasons)


def test_recommend_alternatives_no_candidates(sim_test_db):
    """
    Verifies that recommend_alternatives returns an empty list cleanly when
    no other suppliers provide the material.
    """
    engine = SimulationEngine()
    # TyreWorks (supplier_id=2) provides Material 4 (Tyres); no other supplier provides it
    recs = engine.recommend_alternatives(
        supplier_id=2,
        material_id=4,
        db=sim_test_db,
    )
    assert recs == []


def test_simulation_save_persists_to_scenario_tables(sim_test_db, isolated_graph_service):
    """
    Verifies that running with save=True persists records to scenarios and scenario_results tables.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[MitigationInput(type="safety_stock", material_id=1, extra_days=10)],
        scenario_name="Persisted Test Scenario",
        save=True,
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert result.scenario_id is not None

    # Query database to verify persistence
    saved_scen = sim_test_db.query(Scenario).filter(Scenario.id == result.scenario_id).first()
    assert saved_scen is not None
    assert saved_scen.name == "Persisted Test Scenario"
    assert saved_scen.duration_days == 30
    assert saved_scen.failed_supplier_ids == [5]

    # Results: 2 variants (before and after)
    saved_results = sim_test_db.query(ScenarioResult).filter(ScenarioResult.scenario_id == result.scenario_id).all()
    assert len(saved_results) == 2
    variants = {r.variant: r for r in saved_results}
    assert "before_mitigation" in variants
    assert "after_mitigation" in variants
    assert variants["before_mitigation"].lines_at_risk == 2
    assert variants["before_mitigation"].revenue_at_risk == 1944000000.0
    assert variants["after_mitigation"].revenue_at_risk == pytest.approx(984000000.0, rel=1e-3)


# =============================================================================
# Additional Regression and Priority Verification Tests (TASK-025 Review)
# =============================================================================

def test_simulation_reroute_uses_relationship_data_and_discloses_assumption(sim_test_db, isolated_graph_service):
    """
    Priority 1: Verifies that reroute uses confirmed Relationship lead time when present,
    and falls back to configurable default with transparent disclosure when absent.
    """
    engine = SimulationEngine()

    # Case A: Direct relationship exists (SouthAsia #7 -> RubberCore #4 for Natural Latex #1)
    rel_reroute = Relationship(
        id=99,
        supplier_id=7,
        buyer_id=4,
        material_id=1,
        lead_time_days=6,
        status="approved",
    )
    sim_test_db.add(rel_reroute)
    sim_test_db.commit()

    res_rel = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="reroute",
                from_supplier_id=7,
                to_supplier_id=4,
                material_id=1,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )
    assert any("confirmed relationship (6 days)" in n for n in res_rel.notes)

    # Clean up relationship 99
    sim_test_db.delete(rel_reroute)
    sim_test_db.commit()

    # Case B: No relationship and no SupplierMaterial exists (e.g. from TyreWorks #2 to RubberCore #4 for Material 1)
    res_fallback = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="reroute",
                from_supplier_id=2,
                to_supplier_id=4,
                material_id=1,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )
    assert any("default configurable assumption (7 days)" in n for n in res_fallback.notes)


def test_simulation_demand_fallback_transparent(sim_test_db, isolated_graph_service):
    """
    Priority 2: Verifies that missing contracted volume falls back to nominal capacity,
    and missing capacity falls back to unrecorded demand with transparent notes.
    """
    engine = SimulationEngine()

    # Clear contracted volume on Relationship 1
    r1 = sim_test_db.query(Relationship).filter(Relationship.id == 1).first()
    r1.quantity_per_month = None
    sim_test_db.commit()

    # Case A: Falls back to GreenLatex nominal capacity (120.0 MT in SupplierMaterial)
    res_cap = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=7,  # SouthAsia capacity is 90.0 MT -> 90 / 120 = 75% coverage
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )
    assert any("nominal supplier capacity (120.0 units/month)" in n for n in res_cap.notes)
    assert any("capacity coverage 75%" in n for n in res_cap.notes)

    # Case B: Clear SupplierMaterial capacity for GreenLatex
    sm_gl = sim_test_db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == 5, SupplierMaterial.material_id == 1).first()
    sm_gl.capacity_per_month = None
    sim_test_db.commit()

    res_unrecorded = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=7,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )
    assert any("unrecorded across failed suppliers; assuming full capacity coverage" in n for n in res_unrecorded.notes)
    assert any("capacity coverage 100% based on unrecorded demand" in n for n in res_unrecorded.notes)


def test_simulation_alternate_lead_fallback_transparent(sim_test_db, isolated_graph_service):
    """
    Priority 3: Verifies that alternate supplier without catalog lead time or relationship
    uses configurable default and discloses it in notes.
    """
    # Create supplier 8 with no typical_lead_time_days in SupplierMaterial
    s_new = Supplier(id=8, name="Global Latex Ltd", country="India", region="South Asia", is_active=True, base_risk=20.0, entity_type="supplier")
    sm_new = SupplierMaterial(supplier_id=8, material_id=1, capacity_per_month=100.0, typical_lead_time_days=None, is_qualified=True)
    sim_test_db.add_all([s_new, sm_new])
    sim_test_db.commit()

    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=8,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert any("has no recorded lead time for Natural Latex; using default configurable assumption (14 days)" in n for n in result.notes)


def test_simulation_multiple_simultaneous_failed_suppliers(sim_test_db, isolated_graph_service):
    """
    Priority 4: Verifies concurrent outage across multiple suppliers (Tier 3 GreenLatex and Tier 1 TyreWorks).
    Line A is impacted by both: Tier 1 TyreWorks has 3-day buffer (earlier than 9-day GreenLatex path).
    Unbuffered days = 30 - 3 = 27 days -> 27 * 60M = 1,620,000,000 INR.
    Line B is impacted by GreenLatex -> 19 unbuffered days * 36M = 684,000,000 INR.
    Total before mitigation = 2,304,000,000 INR.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5, 2],
        duration_days=30,
        mitigations=[],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert any("Simulating concurrent multi-supplier disruption across 2 suppliers" in n for n in result.notes)
    assert result.before_mitigation.lines_at_risk == 2
    assert result.before_mitigation.days_to_impact == 3  # TyreWorks 3-day buffer is the earliest impact
    assert result.before_mitigation.revenue_at_risk == pytest.approx(2304000000.0, rel=1e-3)


def test_simulation_safety_stock_on_oem_component_material(sim_test_db, isolated_graph_service):
    """
    Priority 5: Verifies that safety stock added for OEM component material (Tyres: ID 4)
    extends Line A's buffer directly without double counting or affecting Line B (Rubber Seals: ID 5).
    Line A buffer increases from 9 to 14 days (5 extra days).
    Line B buffer remains 11 days.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="safety_stock",
                material_id=4,  # Tyres delivered directly to Line A
                extra_days=5,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Line A downtime reduced by 5 days -> 5 * 60M = 300,000,000 protected
    line_a = next(l for l in result.after_mitigation.lines if l.line_id == 1)
    line_b = next(l for l in result.after_mitigation.lines if l.line_id == 2)

    assert line_a.days_to_impact == 14  # 9 + 5
    assert line_a.unbuffered_days == 16  # 30 - 14
    assert line_b.days_to_impact == 11  # Unaffected by Tyres safety stock
    assert line_b.unbuffered_days == 19  # 30 - 11

    assert result.improvement.revenue_protected == pytest.approx(300000000.0, rel=1e-3)
    assert any("Added 5 days safety stock buffer for Tyres" in n for n in result.notes)


def test_simulation_capacity_coverage_full_vs_partial_share_pct(sim_test_db, isolated_graph_service):
    """
    Priority 6: Verifies capacity coverage formula min(avail_cap / req_vol, share_pct / 100).
    With req_vol = 90 MT and avail_cap = 90 MT:
    - 100% share yields 100% capacity coverage (no capacity deficit).
    - 50% share yields 50% capacity coverage (post-arrival 16 days * 50% = 8 days deficit on Line A).
    """
    engine = SimulationEngine()

    # Full share (100%)
    res_full = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=7,
                share_pct=100.0,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Partial share (50%)
    res_partial = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=30,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=7,
                share_pct=50.0,
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Full share has only lead time gap (5 days on Line A -> 300M, 3 days on Line B -> 108M = 408M)
    assert res_full.after_mitigation.revenue_at_risk == pytest.approx(408000000.0, rel=1e-3)

    # Partial share has lead time gap + 8 days capacity deficit on Line A (13d * 60M = 780M)
    # and Line B (3d lead gap + 8d deficit = 11d * 36M = 396M) -> Total = 1,176,000,000 INR
    assert res_partial.after_mitigation.revenue_at_risk == pytest.approx(1176000000.0, rel=1e-3)
    assert res_partial.after_mitigation.revenue_at_risk > res_full.after_mitigation.revenue_at_risk


def test_simulation_alternate_lead_greater_than_duration(sim_test_db, isolated_graph_service):
    """
    Priority 7a: Verifies that when alternate supplier lead time (14 days) exceeds disruption duration (12 days),
    it arrives after the disruption is over, resulting in zero protection.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=12,
        mitigations=[
            MitigationInput(
                type="alternate_supplier",
                material_id=1,
                supplier_id=7,  # 14-day lead time > 12-day outage
            )
        ],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    # Line A: 12 - 9 = 3 unbuffered days * 60M = 180,000,000
    # Line B: 12 - 11 = 1 unbuffered day * 36M = 36,000,000
    # Total = 216,000,000 before and after
    assert result.before_mitigation.revenue_at_risk == pytest.approx(216000000.0, rel=1e-3)
    assert result.after_mitigation.revenue_at_risk == pytest.approx(216000000.0, rel=1e-3)
    assert result.improvement.revenue_protected == 0.0
    assert any("Applied mitigations were insufficient" in n for n in result.notes)


def test_simulation_duration_equal_to_inventory_buffer(sim_test_db, isolated_graph_service):
    """
    Priority 7b: Verifies that when disruption duration exactly equals cumulative buffer (9 days),
    unbuffered days are 0 and revenue at risk is 0.0.
    """
    engine = SimulationEngine()
    result = engine.run_simulation(
        failed_supplier_ids=[5],
        duration_days=9,  # Matches Line A buffer (9 days) and is less than Line B (11 days)
        mitigations=[],
        db=sim_test_db,
        graph_service=isolated_graph_service,
    )

    assert result.before_mitigation.lines_at_risk == 0
    assert result.before_mitigation.revenue_at_risk == 0.0
    assert result.before_mitigation.days_to_impact is None


def test_recommend_alternatives_deterministic_ranking_with_tied_scores(sim_test_db):
    """
    Priority 7c: Verifies deterministic ranking when candidates share identical scores.
    Breaks ties by lead_time_days ascending, then supplier_id ascending.
    """
    # Add two new suppliers with identical attributes
    s10 = Supplier(id=10, name="Alpha Latex Ltd", country="India", region="South Asia", is_active=True, base_risk=20.0, entity_type="supplier")
    s11 = Supplier(id=11, name="Beta Latex Ltd", country="India", region="South Asia", is_active=True, base_risk=20.0, entity_type="supplier")
    sm10 = SupplierMaterial(supplier_id=10, material_id=1, capacity_per_month=90.0, typical_lead_time_days=14, is_qualified=True)
    sm11 = SupplierMaterial(supplier_id=11, material_id=1, capacity_per_month=90.0, typical_lead_time_days=14, is_qualified=True)
    sim_test_db.add_all([s10, s11, sm10, sm11])
    sim_test_db.commit()

    engine = SimulationEngine()
    recs = engine.recommend_alternatives(
        supplier_id=5,
        material_id=1,
        limit=5,
        db=sim_test_db,
    )

    # Verify deterministic ordering: SouthAsia (#7), then Alpha (#10), then Beta (#11)
    # SouthAsia #7 has an existing relationship, giving it a slightly higher familiarity score
    assert len(recs) == 3
    rec_ids = [r.supplier_id for r in recs]
    assert rec_ids[0] == 7   # Higher score due to existing relationship
    assert rec_ids[1] == 10  # Tied score with #11, but lower supplier_id
    assert rec_ids[2] == 11
    assert recs[1].score == recs[2].score
    assert recs[1].rank == 2
    assert recs[2].rank == 3
