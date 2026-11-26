"""
API endpoints for Graph and Dependency analysis (TASK-010).
Conforms to project-docs/API_SPEC.md Section 4.5 and project-docs/ARCHITECTURE.md Section 3.4 & 3.5.
"""

from typing import Optional, List, Dict, Set, Any, Union
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.db import (
    Supplier,
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
    ManufacturerNotFoundError,
    MultipleManufacturersError,
    to_node_id,
    parse_supplier_id,
)
from backend.graph.analyzer import DependencyAnalyzer
from backend.models.schemas import (
    GraphResponse,
    GraphNodeItem,
    GraphEdgeItem,
    GraphMeta,
    GraphRebuildResponse,
    NodeDetailResponse,
    NodeNeighborRef,
    NodeReaches,
    NodeEvidenceItem,
    DependencyResponse,
    DependencyItem,
)

router = APIRouter(tags=["Graph"])


# =============================================================================
# POST /graph/rebuild
# =============================================================================

@router.post("/graph/rebuild", response_model=GraphRebuildResponse)
def rebuild_graph(db: Session = Depends(get_db)) -> Union[GraphRebuildResponse, JSONResponse]:
    """
    Rebuilds the in-memory graph from approved relationships, recomputes tiers
    relative to the manufacturer, synchronizes tiers to relationships.tier,
    and runs cycle detection.
    """
    try:
        summary = graph_service.rebuild(db)
        built_dt = (
            datetime.fromisoformat(summary["built_at"])
            if isinstance(summary["built_at"], str)
            else summary["built_at"]
        )
        return GraphRebuildResponse(
            nodes=summary["nodes"],
            edges=summary["edges"],
            max_tier=summary["max_tier"],
            built_at=built_dt,
        )
    except ManufacturerNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(e),
                    "details": {},
                }
            },
        )
    except MultipleManufacturersError as e:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "details": {},
                }
            },
        )


# =============================================================================
# GET /graph
# =============================================================================

@router.get("/graph", response_model=GraphResponse)
def get_graph(
    tier_max: Optional[int] = Query(default=None, ge=0, description="Include tiers up to this value"),
    region: Optional[str] = Query(default=None, description="Filter by supplier region"),
    material_id: Optional[int] = Query(default=None, ge=1, description="Only chains involving this material"),
    min_risk: Optional[float] = Query(default=None, ge=0.0, le=100.0, description="Filter by minimum risk score"),
    include_pending: bool = Query(default=False, description="Overlay pending relationships as dashed edges"),
    db: Session = Depends(get_db),
) -> GraphResponse:
    """
    Returns graph nodes (suppliers and production lines) and directed edges
    formatted for frontend rendering (React Flow / Cytoscape).
    """
    # Normalize parameters for direct programmatic invocations
    actual_tier_max = tier_max if isinstance(tier_max, int) else None
    actual_region = region if isinstance(region, str) and region.strip() else None
    actual_material_id = material_id if isinstance(material_id, int) else None
    actual_min_risk = float(min_risk) if isinstance(min_risk, (int, float)) else None
    actual_include_pending = bool(include_pending) if isinstance(include_pending, bool) else False

    # Build on-demand if the graph has not been built yet
    if not graph_service.is_built:
        try:
            graph_service.rebuild(db)
        except Exception:
            pass

    # 1. Active open alerts for suppliers
    supplier_alerts = (
        db.query(DisruptionEvent.supplier_id, Alert.risk_score)
        .join(Alert, Alert.event_id == DisruptionEvent.id)
        .filter(Alert.status == "open")
        .order_by(Alert.risk_score.desc())
        .all()
    )
    supplier_alert_map: Dict[int, float] = {}
    for sid, score in supplier_alerts:
        if sid not in supplier_alert_map:
            supplier_alert_map[sid] = float(score)

    # 2. Active open alerts for production lines
    line_alerts = (
        db.query(AlertAffectedNode.node_id, Alert.risk_score)
        .join(Alert, Alert.id == AlertAffectedNode.alert_id)
        .filter(AlertAffectedNode.node_type == "line", Alert.status == "open")
        .order_by(Alert.risk_score.desc())
        .all()
    )
    line_alert_map: Dict[int, float] = {}
    for lid, score in line_alerts:
        if lid not in line_alert_map:
            line_alert_map[lid] = float(score)

    # 3. Vulnerability flags from DependencyAnalyzer
    flags_map = DependencyAnalyzer.get_supplier_vulnerability_flags(db, graph_service)

    # 4. Materials filter set (if material_id is specified)
    material_supplier_ids: Optional[Set[int]] = None
    material_line_ids: Optional[Set[int]] = None
    if actual_material_id is not None:
        mat_rels = (
            db.query(Relationship.supplier_id, Relationship.buyer_id)
            .filter(
                Relationship.material_id == actual_material_id,
                Relationship.status.in_(["approved", "pending"] if actual_include_pending else ["approved"]),
            )
            .all()
        )
        material_supplier_ids = {r[0] for r in mat_rels} | {r[1] for r in mat_rels}

        # Check which lines require this material
        line_reqs = (
            db.query(LineRequirement.line_id)
            .filter(LineRequirement.material_id == actual_material_id)
            .all()
        )
        material_line_ids = {lr[0] for lr in line_reqs}

    nodes: List[GraphNodeItem] = []
    included_supplier_ids: Set[int] = set()

    # Load active suppliers
    active_suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
    for s in active_suppliers:
        # Material filter
        if material_supplier_ids is not None and s.id not in material_supplier_ids:
            continue

        # Region filter
        if actual_region is not None:
            if not s.region or s.region.strip().lower() != actual_region.strip().lower():
                continue

        # Tier calculation
        node_data = graph_service.get_node_data(s.id)
        if s.entity_type == "manufacturer":
            s_tier = 0
        else:
            s_tier = node_data.get("tier") if node_data else None

        # Tier max filter
        if actual_tier_max is not None:
            if s_tier is None or s_tier > actual_tier_max:
                continue

        # Risk score calculation
        risk_score = supplier_alert_map.get(s.id, float(s.base_risk or 0.0))

        # Min risk filter
        if actual_min_risk is not None and risk_score < actual_min_risk:
            continue

        nodes.append(
            GraphNodeItem(
                id=to_node_id(s.id),
                type="supplier",
                label=s.name,
                tier=s_tier,
                region=s.region,
                risk_score=risk_score,
                flags=flags_map.get(s.id, []),
            )
        )
        included_supplier_ids.add(s.id)

    # Load production lines
    prod_lines = (
        db.query(ProductionLine)
        .join(Plant, ProductionLine.plant_id == Plant.id)
        .all()
    )
    for line in prod_lines:
        if material_line_ids is not None and line.id not in material_line_ids:
            continue

        line_tier = 0
        if actual_tier_max is not None and line_tier > actual_tier_max:
            continue

        line_risk = line_alert_map.get(line.id, 0.0)
        if actual_min_risk is not None and line_risk < actual_min_risk:
            continue

        label_name = f"{line.name} ({line.product.name})" if line.product else line.name
        plant_loc = line.plant.location if line.plant else None

        # Region filter: compare requested region case-insensitively against actual Plant.location
        if actual_region is not None:
            if not plant_loc or actual_region.strip().lower() not in plant_loc.strip().lower():
                continue

        nodes.append(
            GraphNodeItem(
                id=f"line:{line.id}",
                type="line",
                label=label_name,
                tier=line_tier,
                region=plant_loc,
                risk_score=line_risk,
                flags=[],
            )
        )

    # Load approved edges between included active suppliers
    edges: List[GraphEdgeItem] = []
    approved_query = db.query(Relationship).filter(Relationship.status == "approved")
    if actual_material_id is not None:
        approved_query = approved_query.filter(Relationship.material_id == actual_material_id)

    for r in approved_query.all():
        if r.supplier_id in included_supplier_ids and r.buyer_id in included_supplier_ids:
            edges.append(
                GraphEdgeItem(
                    id=f"rel:{r.id}",
                    source=to_node_id(r.supplier_id),
                    target=to_node_id(r.buyer_id),
                    material=r.material.name if r.material else "",
                    lead_time_days=r.lead_time_days,
                    share_pct=r.share_pct,
                    confidence=r.confidence,
                    status="approved",
                )
            )

    # Load pending edges overlay if requested
    if actual_include_pending:
        pending_query = db.query(Relationship).filter(Relationship.status == "pending")
        if actual_material_id is not None:
            pending_query = pending_query.filter(Relationship.material_id == actual_material_id)

        for r in pending_query.all():
            if r.supplier_id in included_supplier_ids and r.buyer_id in included_supplier_ids:
                edges.append(
                    GraphEdgeItem(
                        id=f"rel:{r.id}",
                        source=to_node_id(r.supplier_id),
                        target=to_node_id(r.buyer_id),
                        material=r.material.name if r.material else "",
                        lead_time_days=r.lead_time_days,
                        share_pct=r.share_pct,
                        confidence=r.confidence,
                        status="pending",
                    )
                )

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        meta=GraphMeta(built_at=graph_service.built_at),
    )


# =============================================================================
# GET /graph/node/{node_type}/{id}
# =============================================================================

@router.get("/graph/node/{node_type}/{id}", response_model=NodeDetailResponse)
def get_node_detail(
    node_type: str = Path(..., description="Node type: 'supplier' or 'line'"),
    id: int = Path(..., ge=1, description="Entity database ID (>= 1)"),
    db: Session = Depends(get_db),
) -> Union[NodeDetailResponse, JSONResponse]:
    """
    Returns detailed node attributes, risk breakdown, upstream suppliers,
    downstream buyers, reachable entities and linked document evidence.
    """
    norm_type = node_type.strip().lower()
    if norm_type not in ("supplier", "line"):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field-level validation failed.",
                    "details": {"node_type": "Must be either 'supplier' or 'line'."},
                }
            },
        )

    # Build on-demand if the graph has not been built yet
    if not graph_service.is_built:
        try:
            graph_service.rebuild(db)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Case 1: Supplier Node
    # -------------------------------------------------------------------------
    if norm_type == "supplier":
        s = db.query(Supplier).filter(Supplier.id == id, Supplier.is_active == True).first()
        if not s:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Supplier {id} does not exist or is inactive.",
                        "details": {},
                    }
                },
            )

        # Risk score and breakdown
        active_alert = (
            db.query(Alert)
            .join(DisruptionEvent, Alert.event_id == DisruptionEvent.id)
            .filter(DisruptionEvent.supplier_id == s.id, Alert.status == "open")
            .order_by(Alert.risk_score.desc())
            .first()
        )
        risk_score = float(active_alert.risk_score) if active_alert else float(s.base_risk or 0.0)
        risk_breakdown = (
            active_alert.score_breakdown
            if (active_alert and isinstance(active_alert.score_breakdown, dict))
            else {}
        )

        # Tier
        node_data = graph_service.get_node_data(s.id)
        if s.entity_type == "manufacturer":
            s_tier = 0
        else:
            s_tier = node_data.get("tier") if node_data else None

        # Upstream direct suppliers
        pred_ids = graph_service.get_direct_suppliers(s.id)
        upstream_list: List[NodeNeighborRef] = []
        for p_id in pred_ids:
            rel = (
                db.query(Relationship)
                .filter(
                    Relationship.supplier_id == p_id,
                    Relationship.buyer_id == s.id,
                    Relationship.status == "approved",
                )
                .first()
            )
            mat_name = rel.material.name if (rel and rel.material) else None
            p_supp = db.query(Supplier).filter(Supplier.id == p_id).first()
            upstream_list.append(
                NodeNeighborRef(
                    id=to_node_id(p_id),
                    label=p_supp.name if p_supp else f"Supplier {p_id}",
                    material=mat_name,
                )
            )

        # Downstream direct buyers
        succ_ids = graph_service.get_direct_buyers(s.id)
        downstream_list: List[NodeNeighborRef] = []
        for succ_id in succ_ids:
            rel = (
                db.query(Relationship)
                .filter(
                    Relationship.supplier_id == s.id,
                    Relationship.buyer_id == succ_id,
                    Relationship.status == "approved",
                )
                .first()
            )
            mat_name = rel.material.name if (rel and rel.material) else None
            succ_supp = db.query(Supplier).filter(Supplier.id == succ_id).first()
            downstream_list.append(
                NodeNeighborRef(
                    id=to_node_id(succ_id),
                    label=succ_supp.name if succ_supp else f"Supplier {succ_id}",
                    material=mat_name,
                )
            )

        # Reaches (Tier 1 suppliers and production lines)
        descendants = graph_service.get_downstream_descendants(s.id)
        tier1_suppliers_set: Set[str] = set()
        tier1_ids: Set[int] = set()

        if s_tier == 1:
            tier1_suppliers_set.add(s.name)
            tier1_ids.add(s.id)
        else:
            for d_id in descendants:
                d_node = graph_service.get_node_data(d_id)
                if d_node and d_node.get("tier") == 1:
                    d_supp = db.query(Supplier).filter(Supplier.id == d_id).first()
                    if d_supp:
                        tier1_suppliers_set.add(d_supp.name)
                        tier1_ids.add(d_id)

        # Production lines reached via those Tier 1 suppliers
        production_lines_set: Set[str] = set()
        mfg_id = graph_service.manufacturer_id
        if mfg_id is not None and tier1_ids:
            materials_to_mfg = (
                db.query(Relationship.material_id)
                .filter(
                    Relationship.status == "approved",
                    Relationship.supplier_id.in_(tier1_ids),
                    Relationship.buyer_id == mfg_id,
                )
                .all()
            )
            mat_ids = [m[0] for m in materials_to_mfg]
            if mat_ids:
                lines = (
                    db.query(ProductionLine.name)
                    .join(LineRequirement, ProductionLine.id == LineRequirement.line_id)
                    .filter(LineRequirement.material_id.in_(mat_ids))
                    .all()
                )
                for l in lines:
                    production_lines_set.add(l[0])

        reaches = NodeReaches(
            tier1_suppliers=sorted(tier1_suppliers_set),
            production_lines=sorted(production_lines_set),
        )

        # Evidence retrieval: incident relationships
        rel_ids = [
            r[0]
            for r in db.query(Relationship.id)
            .filter(
                Relationship.status == "approved",
                (Relationship.supplier_id == s.id) | (Relationship.buyer_id == s.id),
            )
            .all()
        ]

        seen_ev: Set[Tuple[str, Optional[int], str]] = set()
        evidence_list: List[NodeEvidenceItem] = []

        if rel_ids:
            # 1. Multi-evidence junction records
            junction_ev = (
                db.query(Document.filename, Evidence.page, Evidence.snippet, Evidence.llm_confidence)
                .join(RelationshipEvidence, RelationshipEvidence.evidence_id == Evidence.id)
                .join(Document, Evidence.document_id == Document.id)
                .filter(RelationshipEvidence.relationship_id.in_(rel_ids))
                .all()
            )
            for fn, page, snippet, conf in junction_ev:
                key = (fn, page, snippet)
                if key not in seen_ev:
                    seen_ev.add(key)
                    evidence_list.append(
                        NodeEvidenceItem(
                            document=fn,
                            page=page,
                            snippet=snippet,
                            confidence=float(conf) if conf is not None else None,
                        )
                    )

            # 2. Primary fallback evidence records
            primary_ev = (
                db.query(Document.filename, Evidence.page, Evidence.snippet, Evidence.llm_confidence)
                .join(Relationship, Relationship.evidence_id == Evidence.id)
                .join(Document, Evidence.document_id == Document.id)
                .filter(Relationship.id.in_(rel_ids))
                .all()
            )
            for fn, page, snippet, conf in primary_ev:
                key = (fn, page, snippet)
                if key not in seen_ev:
                    seen_ev.add(key)
                    evidence_list.append(
                        NodeEvidenceItem(
                            document=fn,
                            page=page,
                            snippet=snippet,
                            confidence=float(conf) if conf is not None else None,
                        )
                    )

        return NodeDetailResponse(
            id=to_node_id(s.id),
            type="supplier",
            label=s.name,
            tier=s_tier,
            risk_score=risk_score,
            risk_breakdown=risk_breakdown,
            upstream=upstream_list,
            downstream=downstream_list,
            reaches=reaches,
            evidence=evidence_list,
        )

    # -------------------------------------------------------------------------
    # Case 2: Production Line Node
    # -------------------------------------------------------------------------
    line = db.query(ProductionLine).filter(ProductionLine.id == id).first()
    if not line:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Production line {id} does not exist.",
                    "details": {},
                }
            },
        )

    # Line alert risk
    line_alert = (
        db.query(Alert)
        .join(AlertAffectedNode, Alert.id == AlertAffectedNode.alert_id)
        .filter(
            AlertAffectedNode.node_type == "line",
            AlertAffectedNode.node_id == line.id,
            Alert.status == "open",
        )
        .order_by(Alert.risk_score.desc())
        .first()
    )
    risk_score = float(line_alert.risk_score) if line_alert else 0.0
    risk_breakdown = (
        line_alert.score_breakdown
        if (line_alert and isinstance(line_alert.score_breakdown, dict))
        else {}
    )

    label_name = f"{line.name} ({line.product.name})" if line.product else line.name

    # Upstream Tier 1 suppliers supplying materials for this line
    mfg_id = graph_service.manufacturer_id
    upstream_list = []
    line_reqs = db.query(LineRequirement.material_id).filter(LineRequirement.line_id == line.id).all()
    req_mat_ids = [lr[0] for lr in line_reqs]

    if mfg_id is not None and req_mat_ids:
        t1_rels = (
            db.query(Relationship)
            .join(Supplier, Relationship.supplier_id == Supplier.id)
            .filter(
                Relationship.status == "approved",
                Relationship.buyer_id == mfg_id,
                Relationship.material_id.in_(req_mat_ids),
                Supplier.is_active == True,
            )
            .all()
        )
        for r in t1_rels:
            upstream_list.append(
                NodeNeighborRef(
                    id=to_node_id(r.supplier_id),
                    label=r.supplier.name,
                    material=r.material.name if r.material else None,
                )
            )

    return NodeDetailResponse(
        id=f"line:{line.id}",
        type="line",
        label=label_name,
        tier=0,
        risk_score=risk_score,
        risk_breakdown=risk_breakdown,
        upstream=upstream_list,
        downstream=[],
        reaches=NodeReaches(tier1_suppliers=[], production_lines=[line.name]),
        evidence=[],
    )


# =============================================================================
# GET /dependencies
# =============================================================================

@router.get("/dependencies", response_model=DependencyResponse)
def get_dependencies(
    type: Optional[str] = Query(default=None, description="Filter by dependency type"),
    min_severity: Optional[str] = Query(default=None, description="Filter by minimum severity ('low', 'medium', 'high', 'critical')"),
    db: Session = Depends(get_db),
) -> DependencyResponse:
    """
    Identifies hidden structural vulnerabilities and single points of failure
    across the active supply chain graph.
    """
    # Normalize parameters for direct programmatic invocations
    actual_type = type if isinstance(type, str) and type.strip() else None
    actual_min_severity = min_severity if isinstance(min_severity, str) and min_severity.strip() else None

    if not graph_service.is_built:
        try:
            graph_service.rebuild(db)
        except Exception:
            pass

    all_items = DependencyAnalyzer.analyze(db, graph_service)

    # Filter by type if provided
    if actual_type is not None:
        norm_type = actual_type.strip().lower()
        all_items = [i for i in all_items if i.type == norm_type]

    # Filter by min_severity if provided
    if actual_min_severity is not None:
        severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        target_rank = severity_rank.get(actual_min_severity.strip().lower(), 1)
        all_items = [i for i in all_items if severity_rank.get(i.severity, 1) >= target_rank]

    return DependencyResponse(items=all_items, total=len(all_items))
