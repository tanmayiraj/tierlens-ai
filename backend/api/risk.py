"""
API endpoints for Risk Analysis, Events, Alerts, Impact Tracing, and Risk Summary (TASK-017).
Conforms strictly to project-docs/API_SPEC.md Sections 4.6, 4.7, and 4.10.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import networkx as nx

from backend.database import get_db
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
from backend.graph.service import (
    graph_service,
    to_node_id,
    parse_supplier_id,
)
from backend.graph.analyzer import DependencyAnalyzer
from backend.services.risk_engine import RiskEngine
from backend.models.schemas import (
    EventCreateRequest,
    EventCreateResponse,
    EventListResponse,
    EventListItem,
    EventSupplierRef,
    AlertListResponse,
    AlertListItem,
    AlertDetailResponse,
    AlertEventDetail,
    AlertAffectedNodeItem,
    AlertEvidenceItem,
    AlertUpdateStatusRequest,
    AlertUpdateStatusResponse,
    ImpactResponse,
    ImpactOrigin,
    ImpactSummary,
    ImpactPathItem,
    ImpactAffectedNode,
    RiskSummaryResponse,
    RiskSummaryNetwork,
    RiskSummaryOpenAlerts,
    TopRiskySupplierItem,
)

router = APIRouter(tags=["Risk & Disruptions"])


# =============================================================================
# 1. POST /events — Log Disruption & Generate Alert
# =============================================================================

@router.post("/events", status_code=status.HTTP_201_CREATED, response_model=EventCreateResponse)
def create_event(
    payload: EventCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Logs a disruption event and automatically executes risk evaluation,
    downstream impact analysis, and alert generation.
    """
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == payload.supplier_id, Supplier.is_active == True)
        .first()
    )
    if not supplier:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Supplier {payload.supplier_id} was not found or is inactive.",
                    "details": {},
                }
            },
        )

    event = DisruptionEvent(
        supplier_id=payload.supplier_id,
        event_type=payload.event_type,
        severity=payload.severity,
        start_date=payload.start_date,
        expected_duration_days=payload.expected_duration_days,
        description=payload.description,
        source=payload.source,
        is_simulated=payload.is_simulated,
    )
    db.add(event)
    db.flush()

    gs = graph_service
    if not gs.is_built:
        gs.rebuild(db)

    engine = RiskEngine()
    result = engine.evaluate_event(event, db, gs)
    alert = engine.persist_alert(event, result, db)
    db.commit()
    db.refresh(event)
    db.refresh(alert)

    return EventCreateResponse(
        event_id=event.id,
        alert_id=alert.id,
        severity_label=alert.severity_label,
        risk_score=alert.risk_score,
    )


# =============================================================================
# 2. GET /events — List Disruption Events
# =============================================================================

@router.get("/events", response_model=EventListResponse)
def list_events(
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    is_simulated: Optional[bool] = Query(None, description="Filter simulated vs real events"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    Lists disruption events with optional filtering and pagination.
    """
    actual_supplier_id = supplier_id if isinstance(supplier_id, int) else None
    actual_event_type = event_type if isinstance(event_type, str) else None
    actual_is_simulated = is_simulated if isinstance(is_simulated, bool) else None
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0

    query = db.query(DisruptionEvent).join(Supplier, DisruptionEvent.supplier_id == Supplier.id)

    if actual_supplier_id is not None:
        query = query.filter(DisruptionEvent.supplier_id == actual_supplier_id)
    if actual_event_type is not None:
        query = query.filter(DisruptionEvent.event_type == actual_event_type)
    if actual_is_simulated is not None:
        query = query.filter(DisruptionEvent.is_simulated == actual_is_simulated)

    total = query.count()
    events = (
        query.order_by(DisruptionEvent.created_at.desc(), DisruptionEvent.id.desc())
        .offset(actual_offset)
        .limit(actual_limit)
        .all()
    )

    items = [
        EventListItem(
            id=ev.id,
            supplier=EventSupplierRef(id=ev.supplier.id, name=ev.supplier.name),
            event_type=ev.event_type,
            severity=ev.severity,
            start_date=ev.start_date,
            expected_duration_days=ev.expected_duration_days,
            description=ev.description,
            source=ev.source,
            is_simulated=ev.is_simulated,
            created_at=ev.created_at,
        )
        for ev in events
    ]

    return EventListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# 3. GET /alerts — List Disruption Alerts
# =============================================================================

@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    status: Optional[str] = Query(None, description="Filter by alert status ('open', 'investigating', 'acknowledged', 'resolved')"),
    severity_label: Optional[str] = Query(None, description="Filter by severity ('low', 'medium', 'high', 'critical')"),
    supplier_id: Optional[int] = Query(None, description="Filter by origin supplier ID"),
    sort: str = Query("risk_score:desc", description="Sort expression: field:asc|desc"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    Lists risk disruption alerts with severity, status, and supplier filters.
    """
    actual_status = status if isinstance(status, str) and status.strip() else None
    actual_severity_label = severity_label if isinstance(severity_label, str) and severity_label.strip() else None
    actual_supplier_id = supplier_id if isinstance(supplier_id, int) else None
    actual_sort = sort if isinstance(sort, str) else "risk_score:desc"
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0

    query = (
        db.query(Alert)
        .join(DisruptionEvent, Alert.event_id == DisruptionEvent.id)
        .join(Supplier, DisruptionEvent.supplier_id == Supplier.id)
    )

    if actual_status:
        query = query.filter(Alert.status == actual_status)
    if actual_severity_label:
        query = query.filter(Alert.severity_label == actual_severity_label)
    if actual_supplier_id is not None:
        query = query.filter(DisruptionEvent.supplier_id == actual_supplier_id)

    # Parse sort expression
    sort_field, sort_dir = ("risk_score", "desc")
    if ":" in actual_sort:
        parts = actual_sort.split(":")
        sort_field = parts[0]
        sort_dir = parts[1].lower() if len(parts) > 1 else "desc"

    if sort_field == "created_at":
        order_col = Alert.created_at.desc() if sort_dir == "desc" else Alert.created_at.asc()
    elif sort_field == "days_to_impact":
        order_col = Alert.days_to_impact.desc() if sort_dir == "desc" else Alert.days_to_impact.asc()
    elif sort_field == "revenue_at_risk":
        order_col = Alert.revenue_at_risk.desc() if sort_dir == "desc" else Alert.revenue_at_risk.asc()
    else:  # default risk_score
        order_col = Alert.risk_score.desc() if sort_dir == "desc" else Alert.risk_score.asc()

    total = query.count()
    alerts = query.order_by(order_col, Alert.id.desc()).offset(actual_offset).limit(actual_limit).all()

    items = [
        AlertListItem(
            id=a.id,
            event_id=a.event_id,
            supplier=a.event.supplier.name,
            supplier_id=a.event.supplier_id,
            severity_label=a.severity_label,
            risk_score=a.risk_score,
            days_to_impact=a.days_to_impact,
            revenue_at_risk=a.revenue_at_risk,
            status=a.status,
            created_at=a.created_at,
        )
        for a in alerts
    ]

    return AlertListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# 4. GET /alerts/{id} — Detailed Alert View
# =============================================================================

@router.get("/alerts/{id}", response_model=AlertDetailResponse)
def get_alert_detail(
    id: int = Path(..., ge=1, description="Alert ID"),
    db: Session = Depends(get_db),
):
    """
    Returns complete alert details, including score breakdown, affected graph nodes,
    and linked document evidence snippets.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Alert {id} does not exist.",
                    "details": {},
                }
            },
        )

    event = alert.event
    supplier = event.supplier

    # Build affected nodes
    affected_items = []
    for an in alert.affected_nodes:
        name = ""
        if an.node_type == "supplier":
            s = db.query(Supplier).filter(Supplier.id == an.node_id).first()
            name = s.name if s else f"Supplier #{an.node_id}"
        elif an.node_type == "line":
            l = db.query(ProductionLine).filter(ProductionLine.id == an.node_id).first()
            name = l.name if l else f"Line #{an.node_id}"
        elif an.node_type == "material":
            m = db.query(Material).filter(Material.id == an.node_id).first()
            name = m.name if m else f"Material #{an.node_id}"
        elif an.node_type == "product":
            p = db.query(Product).filter(Product.id == an.node_id).first()
            name = p.name if p else f"Product #{an.node_id}"
        else:
            name = f"{an.node_type.capitalize()} #{an.node_id}"

        affected_items.append(
            AlertAffectedNodeItem(
                node_type=an.node_type,
                name=name,
                node_id=an.node_id,
                path_depth=an.path_depth,
                days_to_impact=an.days_to_impact,
            )
        )

    # Fetch document evidence linked to the supplier's approved relationships
    evidence_rows = (
        db.query(Evidence, Document)
        .join(RelationshipEvidence, RelationshipEvidence.evidence_id == Evidence.id)
        .join(Relationship, Relationship.id == RelationshipEvidence.relationship_id)
        .join(Document, Document.id == Evidence.document_id)
        .filter(Relationship.supplier_id == event.supplier_id)
        .distinct()
        .all()
    )

    evidence_items = [
        AlertEvidenceItem(
            document=doc.filename,
            page=ev.page,
            snippet=ev.snippet,
        )
        for ev, doc in evidence_rows
    ]

    return AlertDetailResponse(
        id=alert.id,
        event=AlertEventDetail(
            id=event.id,
            supplier=supplier.name,
            supplier_id=supplier.id,
            event_type=event.event_type,
            expected_duration_days=event.expected_duration_days,
            start_date=event.start_date,
            description=event.description,
        ),
        severity_label=alert.severity_label,
        risk_score=alert.risk_score,
        score_breakdown=alert.score_breakdown or {},
        days_to_impact=alert.days_to_impact,
        revenue_at_risk=alert.revenue_at_risk,
        explanation=alert.explanation,
        affected=affected_items,
        evidence=evidence_items,
        alternatives_url=f"/api/v1/alternatives/{event.supplier_id}",
        status=alert.status,
        created_at=alert.created_at,
    )


# =============================================================================
# 5. PATCH /alerts/{id} — Update Alert Status
# =============================================================================

@router.patch("/alerts/{id}", response_model=AlertUpdateStatusResponse)
def update_alert_status(
    payload: AlertUpdateStatusRequest,
    id: int = Path(..., ge=1, description="Alert ID"),
    db: Session = Depends(get_db),
):
    """
    Updates the lifecycle status of an alert ('open', 'investigating', 'acknowledged', 'resolved').
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Alert {id} does not exist.",
                    "details": {},
                }
            },
        )

    alert.status = payload.status
    db.commit()
    db.refresh(alert)

    return AlertUpdateStatusResponse(
        id=alert.id,
        status=alert.status,
    )


# =============================================================================
# 6. GET /impact/{event_id} — Impact Analysis
# =============================================================================

@router.get("/impact/{event_id}", response_model=ImpactResponse)
def get_impact_analysis(
    event_id: int = Path(..., ge=1, description="Disruption Event ID"),
    db: Session = Depends(get_db),
):
    """
    Returns the complete downstream impact trace from an event origin supplier
    through intermediate tiers to affected OEM assembly lines.
    """
    event = db.query(DisruptionEvent).filter(DisruptionEvent.id == event_id).first()
    if not event:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Disruption event {event_id} does not exist.",
                    "details": {},
                }
            },
        )

    gs = graph_service
    if not gs.is_built:
        gs.rebuild(db)

    origin_supp = db.query(Supplier).filter(Supplier.id == event.supplier_id).first()
    origin_tier = (gs.get_node_data(event.supplier_id) or {}).get("tier")

    engine = RiskEngine()
    duration_days = int(event.expected_duration_days or 0)
    (
        affected_nodes_info,
        affected_lines_info,
        earliest_impact,
        total_rev_at_risk,
    ) = engine.trace_downstream_impact(event.supplier_id, duration_days, db, gs)

    supplier_nodes = [n for n in affected_nodes_info if n.node_type == "supplier"]

    # Calculate affected materials and products
    affected_supp_ids = {n.node_id for n in supplier_nodes}
    affected_supp_ids.add(event.supplier_id)
    affected_materials_count = (
        db.query(Relationship.material_id)
        .filter(Relationship.supplier_id.in_(affected_supp_ids), Relationship.status == "approved")
        .distinct()
        .count()
    )

    affected_line_ids = [l.line_id for l in affected_lines_info]
    affected_products_count = (
        db.query(ProductionLine.product_id)
        .filter(ProductionLine.id.in_(affected_line_ids))
        .distinct()
        .count()
        if affected_line_ids
        else 0
    )

    # Reconstruct path traces to each affected production line
    paths: List[ImpactPathItem] = []
    mfg_id = gs.manufacturer_id

    for line_info in affected_lines_info:
        line_reqs = db.query(LineRequirement).filter(LineRequirement.line_id == line_info.line_id).all()
        line_mat_ids = {lr.material_id for lr in line_reqs}

        direct_suppliers = (
            db.query(Relationship.supplier_id)
            .filter(
                Relationship.buyer_id == mfg_id,
                Relationship.material_id.in_(line_mat_ids),
                Relationship.status == "approved",
            )
            .all()
        )
        direct_supp_ids = {s[0] for s in direct_suppliers}

        origin_node = to_node_id(event.supplier_id)
        found_path_names = None

        for ds_id in direct_supp_ids:
            if event.supplier_id == ds_id:
                found_path_names = [origin_supp.name if origin_supp else f"Supplier #{event.supplier_id}", line_info.line_name]
                break
            elif gs.has_path(event.supplier_id, ds_id):
                supp_path = gs.shortest_path(event.supplier_id, ds_id)
                if supp_path:
                    p_names = []
                    for sid in supp_path:
                        s_obj = db.query(Supplier).filter(Supplier.id == sid).first()
                        p_names.append(s_obj.name if s_obj else f"Supplier #{sid}")
                    p_names.append(line_info.line_name)
                    found_path_names = p_names
                    break

        if not found_path_names:
            found_path_names = [origin_supp.name if origin_supp else f"Supplier #{event.supplier_id}", line_info.line_name]

        paths.append(
            ImpactPathItem(
                nodes=found_path_names,
                days_to_impact=line_info.days_to_impact,
            )
        )

    # Format affected nodes
    affected_nodes_resp: List[ImpactAffectedNode] = []
    for n in affected_nodes_info:
        unbuf = None
        rev = None
        if n.node_type == "line":
            match_l = next((l for l in affected_lines_info if l.line_id == n.node_id), None)
            if match_l:
                unbuf = match_l.unbuffered_days
                rev = match_l.revenue_at_risk

        affected_nodes_resp.append(
            ImpactAffectedNode(
                node_type=n.node_type,
                id=n.node_id,
                name=n.name,
                days_to_impact=n.days_to_impact,
                unbuffered_days=unbuf,
                revenue_at_risk=rev,
            )
        )

    return ImpactResponse(
        event_id=event.id,
        origin=ImpactOrigin(
            id=to_node_id(event.supplier_id),
            label=origin_supp.name if origin_supp else f"Supplier #{event.supplier_id}",
            tier=origin_tier,
        ),
        summary=ImpactSummary(
            suppliers_affected=len(supplier_nodes),
            materials_affected=affected_materials_count,
            lines_affected=len(affected_lines_info),
            products_affected=affected_products_count,
            first_impact_in_days=earliest_impact,
            revenue_at_risk=total_rev_at_risk,
        ),
        paths=paths,
        affected_nodes=affected_nodes_resp,
    )


# =============================================================================
# 7. GET /risk/summary — Overview KPI Metrics
# =============================================================================

@router.get("/risk/summary", response_model=RiskSummaryResponse)
def get_risk_summary(
    db: Session = Depends(get_db),
):
    """
    Returns executive risk summary metrics for the Overview dashboard:
    - Network supplier counts by tier
    - Single-source and hidden dependency counts
    - Open alert counts by severity level
    - Top risky suppliers
    - Total revenue at risk across active alerts
    """
    gs = graph_service
    if not gs.is_built:
        gs.rebuild(db)

    active_suppliers = (
        db.query(Supplier)
        .filter(Supplier.is_active == True, Supplier.entity_type == "supplier")
        .all()
    )

    tier1_count = 0
    tier2_count = 0
    tier3_count = 0
    for s in active_suppliers:
        t = (gs.get_node_data(s.id) or {}).get("tier")
        if t == 1:
            tier1_count += 1
        elif t == 2:
            tier2_count += 1
        elif t == 3:
            tier3_count += 1

    deps = DependencyAnalyzer.analyze(db, gs)
    hidden_deps_count = sum(1 for d in deps if d.type == "shared_upstream_supplier")
    single_sources_count = sum(1 for d in deps if d.type == "single_source_material")

    open_alerts = db.query(Alert).filter(Alert.status == "open").all()
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_rev_at_risk = 0.0

    for a in open_alerts:
        sev = a.severity_label.lower() if a.severity_label else "low"
        if sev in counts:
            counts[sev] += 1
        total_rev_at_risk += float(a.revenue_at_risk or 0.0)

    top_suppliers: List[TopRiskySupplierItem] = []
    for s in active_suppliers:
        latest_alert = (
            db.query(Alert)
            .join(DisruptionEvent, Alert.event_id == DisruptionEvent.id)
            .filter(DisruptionEvent.supplier_id == s.id, Alert.status == "open")
            .order_by(Alert.risk_score.desc())
            .first()
        )
        effective_risk = latest_alert.risk_score if latest_alert else float(s.base_risk or 0.0)
        s_tier = (gs.get_node_data(s.id) or {}).get("tier")

        top_suppliers.append(
            TopRiskySupplierItem(
                id=s.id,
                name=s.name,
                tier=s_tier,
                risk_score=effective_risk,
            )
        )

    top_suppliers.sort(key=lambda x: x.risk_score, reverse=True)

    return RiskSummaryResponse(
        network=RiskSummaryNetwork(
            suppliers=len(active_suppliers),
            tier1=tier1_count,
            tier2=tier2_count,
            tier3=tier3_count,
        ),
        hidden_dependencies=hidden_deps_count,
        single_source_materials=single_sources_count,
        open_alerts=RiskSummaryOpenAlerts(
            critical=counts["critical"],
            high=counts["high"],
            medium=counts["medium"],
            low=counts["low"],
        ),
        top_risky_suppliers=top_suppliers[:5],
        total_revenue_at_risk=total_rev_at_risk,
    )
