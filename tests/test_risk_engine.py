"""
Isolated unit and integration tests for the Risk Analysis Engine (TASK-017).
Validates:
- Approved five-factor formulas and bounds.
- Duration benchmark (37.5 days) scaling.
- Graph-based criticality with direct OEM coupling.
- Single-source exposure tiers.
- Buffer gap and zero-risk buffer absorption.
- Regional risk derived strictly from suppliers.base_risk.
- Line-by-line revenue at risk and days-to-impact calculations.
- Complete evaluation of the GreenLatex reference disruption (resulting in 80.0, Critical).
- Complete isolation from the real tierlens.db using temporary SQLite instances.
"""

import pytest
from datetime import date, datetime
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
    DisruptionEvent,
    Alert,
    AlertAffectedNode,
)
from backend.graph.service import GraphService
from backend.services.risk_engine import RiskEngine


@pytest.fixture
def risk_test_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with the
    standard synthetic automotive supply chain dataset.
    """
    db_file = tmp_path / "test_risk_isolated.db"
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
        sm_sa = SupplierMaterial(supplier_id=7, material_id=1, is_qualified=True)  # uncontracted alternative
        session.add_all([sm_gl, sm_sa])
        session.flush()

        # 4. Plant, Product, Lines
        plant = Plant(id=1, manufacturer_id=1, name="Pune Assembly Plant", location="Pune, Maharashtra, India")
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

        # 6. Approved Relationships with exact inventory buffers
        # Rel 1: GreenLatex -> RubberCore (inventory_days = 5)
        r1 = Relationship(id=1, supplier_id=5, buyer_id=4, material_id=1, inventory_days=5, lead_time_days=21, share_pct=70.0, status="approved")
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


def test_event_severity_formula(risk_test_db):
    """
    Validates Factor 1: Event Severity calculation.
    """
    engine = RiskEngine()

    # Case 1: Reference GreenLatex event (sev=5, dur=30)
    ev_ref = DisruptionEvent(supplier_id=5, event_type="shutdown", severity=5, expected_duration_days=30, start_date=date(2026, 11, 20))
    assert engine.calculate_event_severity(ev_ref) == 24.0

    # Case 2: Minimum event (sev=1, dur=0)
    ev_min = DisruptionEvent(supplier_id=5, event_type="delay", severity=1, expected_duration_days=0, start_date=date(2026, 11, 20))
    assert engine.calculate_event_severity(ev_min) == 4.0

    # Case 3: Moderate event (sev=3, dur=15)
    # base = (3/5)*20 = 12.0; dur = (15/37.5)*5 = 2.0; total = 14.0
    ev_mid = DisruptionEvent(supplier_id=5, event_type="shortage", severity=3, expected_duration_days=15, start_date=date(2026, 11, 20))
    assert engine.calculate_event_severity(ev_mid) == 14.0

    # Case 4: Long duration saturation (sev=5, dur=45 >= 37.5) -> full 25.0
    ev_max = DisruptionEvent(supplier_id=5, event_type="natural_disaster", severity=5, expected_duration_days=45, start_date=date(2026, 11, 20))
    assert engine.calculate_event_severity(ev_max) == 25.0


def test_criticality_formula(risk_test_db):
    """
    Validates Factor 2: Criticality calculation.
    """
    engine = RiskEngine()
    gs = GraphService()
    gs.rebuild(risk_test_db)

    # GreenLatex (Tier 3): reaches 2/2 lines (15.0) + 2/2 Tier 1s (7.0) + direct bonus (0.0) = 22.0
    affected_nodes, affected_lines, _, _ = engine.trace_downstream_impact(5, 30, risk_test_db, gs)
    crit_score = engine.calculate_criticality(5, affected_lines, affected_nodes, risk_test_db, gs)
    assert crit_score == 22.0

    # Tier 1 supplier (TyreWorks, id=2): direct OEM supplier (bonus = 3.0)
    # TyreWorks reaches Line A (1/2 lines = 7.5) + reaches itself as Tier 1 (1/2 = 3.5) + direct bonus (3.0) = 14.0
    tw_nodes, tw_lines, _, _ = engine.trace_downstream_impact(2, 30, risk_test_db, gs)
    tw_crit = engine.calculate_criticality(2, tw_lines, tw_nodes, risk_test_db, gs)
    assert tw_crit == 14.0


def test_single_source_exposure_formula(risk_test_db):
    """
    Validates Factor 3: Single-Source Exposure.
    """
    engine = RiskEngine()
    gs = GraphService()
    gs.rebuild(risk_test_db)

    # GreenLatex supplies Natural Latex (single source on chain, but SouthAsia Latex is qualified alt) -> 20.0
    score = engine.calculate_single_source_exposure(5, risk_test_db, gs)
    assert score == 20.0

    # If alternative is removed, single source with NO alternative gives full 25.0
    risk_test_db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == 7).delete()
    risk_test_db.commit()
    score_no_alt = engine.calculate_single_source_exposure(5, risk_test_db, gs)
    assert score_no_alt == 25.0


def test_buffer_gap_formula(risk_test_db):
    """
    Validates Factor 4: Buffer Gap.
    """
    engine = RiskEngine()

    # GreenLatex: dur=30, buffer=9 -> gap = 21 -> (21/30)*15.0 = 10.5
    assert engine.calculate_buffer_gap(30, 9) == 10.5

    # Absorption: dur=7, buffer=9 -> gap = 0 -> 0.0
    assert engine.calculate_buffer_gap(7, 9) == 0.0

    # Buffer None -> 0.0
    assert engine.calculate_buffer_gap(30, None) == 0.0

    # Zero buffer: dur=30, buffer=0 -> gap = 30 -> (30/30)*15.0 = 15.0
    assert engine.calculate_buffer_gap(30, 0) == 15.0


def test_regional_risk_formula(risk_test_db):
    """
    Validates Factor 5: Regional Risk.
    Strictly derived from suppliers.base_risk without arbitrary adjustments.
    """
    engine = RiskEngine()

    # GreenLatex base_risk = 35.0 -> 10.0 * (35.0 / 100) = 3.5
    assert engine.calculate_regional_risk(5, risk_test_db) == 3.5

    # TyreWorks base_risk = 15.0 -> 10.0 * (15.0 / 100) = 1.5
    assert engine.calculate_regional_risk(2, risk_test_db) == 1.5

    # AutoMotive base_risk = 0.0 -> 0.0
    assert engine.calculate_regional_risk(1, risk_test_db) == 0.0


def test_greenlatex_reference_case_evaluation(risk_test_db):
    """
    End-to-end evaluation of the GreenLatex reference disruption event.
    Confirms exact intermediate numbers and convergence to 80.0 (Critical).
    """
    engine = RiskEngine()
    gs = GraphService()

    event = DisruptionEvent(
        id=1,
        supplier_id=5,
        event_type="shutdown",
        severity=5,
        expected_duration_days=30,
        start_date=date(2026, 11, 20),
        description="Factory closed after regional flooding in plantation district.",
        is_simulated=True,
    )
    risk_test_db.add(event)
    risk_test_db.commit()

    result = engine.evaluate_event(event, risk_test_db, gs)

    # 1. Five factor breakdown check
    assert result.score_breakdown["event_severity"] == 24.0
    assert result.score_breakdown["criticality"] == 22.0
    assert result.score_breakdown["single_source_exposure"] == 20.0
    assert result.score_breakdown["buffer_gap"] == 10.5
    assert result.score_breakdown["regional_risk"] == 3.5
    assert result.score_breakdown["total"] == 80.0

    # 2. Risk Score & Severity Label
    assert result.risk_score == 80.0
    assert result.severity_label == "critical"

    # 3. Days to Impact
    # RubberCore at 5d, TyreWorks at 9d, Line A at 9d -> earliest line impact is 9d
    assert result.days_to_impact == 9

    # 4. Line Impact & Revenue at Risk
    # Line A: 30 - 9 = 21 unbuffered days * 60,000,000 = 1,260,000,000 INR
    # Line B: 30 - 11 = 19 unbuffered days * 36,000,000 = 684,000,000 INR
    # Total = 1,944,000,000 INR
    assert len(result.affected_lines) == 2
    assert result.revenue_at_risk == 1944000000.0

    line_a_info = next(l for l in result.affected_lines if l.line_id == 1)
    assert line_a_info.days_to_impact == 9
    assert line_a_info.unbuffered_days == 21
    assert line_a_info.revenue_at_risk == 1260000000.0

    line_b_info = next(l for l in result.affected_lines if l.line_id == 2)
    assert line_b_info.days_to_impact == 11
    assert line_b_info.unbuffered_days == 19
    assert line_b_info.revenue_at_risk == 684000000.0

    # 5. Downstream Nodes Check
    node_names = {n.name for n in result.affected_nodes}
    assert "RubberCore Industries" in node_names
    assert "TyreWorks Ltd" in node_names
    assert "GripSeal Components" in node_names
    assert "Line A" in node_names
    assert "Line B" in node_names


def test_zero_revenue_when_disruption_fully_absorbed(risk_test_db):
    """
    Validates user correction:
    Revenue at risk must be strictly 0.0 when disruption is fully absorbed.
    """
    engine = RiskEngine()

    # 7-day disruption < 9-day buffer
    event_short = DisruptionEvent(
        id=2,
        supplier_id=5,
        event_type="delay",
        severity=2,
        expected_duration_days=7,
        start_date=date(2026, 11, 20),
        is_simulated=True,
    )
    risk_test_db.add(event_short)
    risk_test_db.commit()

    result = engine.evaluate_event(event_short, risk_test_db)

    # Fully absorbed
    assert result.days_to_impact is None
    assert result.revenue_at_risk == 0.0
    assert result.score_breakdown["buffer_gap"] == 0.0
    assert "fully absorbed by downstream inventory buffers" in result.explanation


def test_persist_alert_records(risk_test_db):
    """
    Validates persistence of Alert and AlertAffectedNode records.
    """
    engine = RiskEngine()

    event = DisruptionEvent(
        id=3,
        supplier_id=5,
        event_type="shutdown",
        severity=5,
        expected_duration_days=30,
        start_date=date(2026, 11, 20),
        is_simulated=True,
    )
    risk_test_db.add(event)
    risk_test_db.commit()

    result = engine.evaluate_event(event, risk_test_db)
    alert = engine.persist_alert(event, result, risk_test_db)

    assert alert.id is not None
    assert alert.risk_score == 80.0
    assert alert.severity_label == "critical"
    assert alert.status == "open"

    # Check affected nodes created in database
    db_affected = risk_test_db.query(AlertAffectedNode).filter(AlertAffectedNode.alert_id == alert.id).all()
    assert len(db_affected) >= 5


@pytest.mark.parametrize(
    "score,expected_severity",
    [
        (0.0, "low"),
        (39.0, "low"),
        (39.9, "low"),
        (40.0, "medium"),
        (59.0, "medium"),
        (59.9, "medium"),
        (60.0, "high"),
        (79.0, "high"),
        (79.9, "high"),
        (80.0, "critical"),
        (100.0, "critical"),
    ],
)
def test_severity_classification_boundaries(score, expected_severity):
    """
    Validates exact severity classification boundaries per DESIGN_SYSTEM.md:
    - Low: 0–39
    - Medium: 40–59
    - High: 60–79
    - Critical: 80–100
    Specifically tests boundary values: 39, 40, 59, 60, 79, and 80.
    """
    assert RiskEngine.classify_severity(score) == expected_severity

