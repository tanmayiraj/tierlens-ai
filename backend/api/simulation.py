"""
API endpoints for Disruption Simulation, What-If Planning, and Alternative Recommender (TASK-025).
Conforms strictly to project-docs/API_SPEC.md Sections 4.8 and 4.9.
Never mutates the live network graph.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.db import (
    Supplier,
    Material,
    Relationship,
    ProductionLine,
    LineRequirement,
    SupplierMaterial,
    Scenario,
    ScenarioResult,
)
from backend.graph.service import graph_service
from backend.services.simulation_engine import (
    SimulationEngine,
    MitigationInput,
    SimulationResult,
    SimulationOutcome,
)
from backend.models.schemas import (
    MitigationSchema,
    SimulationRequest,
    SimulationResponse,
    SimulationOutcomeSchema,
    SimulationLineBreakdownSchema,
    SimulationImprovementSchema,
    ScenarioListItem,
    ScenarioListResponse,
    ScenarioDetailResponse,
    AlternativeSupplierBrief,
    AlternativeMaterialBrief,
    AlternativeItem,
    AlternativesResponse,
)

router = APIRouter(tags=["Simulation & What-If"])


# =============================================================================
# Helper Converters
# =============================================================================

def _build_outcome_schema(outcome: SimulationOutcome) -> SimulationOutcomeSchema:
    """Converts a SimulationOutcome dataclass into a SimulationOutcomeSchema."""
    line_schemas = [
        SimulationLineBreakdownSchema(
            line_id=l.line_id,
            line_name=l.line_name,
            daily_revenue=l.daily_revenue,
            days_to_impact=l.days_to_impact,
            unbuffered_days=l.unbuffered_days,
            revenue_at_risk=l.revenue_at_risk,
        )
        for l in outcome.lines
    ]
    return SimulationOutcomeSchema(
        lines_at_risk=outcome.lines_at_risk,
        revenue_at_risk=outcome.revenue_at_risk,
        days_to_impact=outcome.days_to_impact,
        affected_path=outcome.affected_path,
        lines=line_schemas,
    )


# =============================================================================
# 1. POST /simulate — Run What-If Simulation
# =============================================================================

@router.post("/simulate", response_model=SimulationResponse)
def run_simulation_endpoint(
    payload: SimulationRequest,
    db: Session = Depends(get_db),
):
    """
    Runs a what-if disruption simulation against an isolated copy of the network graph.
    Computes baseline operational exposure, applies configured mitigation actions,
    and returns before/after comparisons and improvement metrics.
    If save=True, persists the scenario and both result variants to database.
    """
    if not payload.failed_supplier_ids:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "failed_supplier_ids must contain at least one supplier ID.",
                }
            },
        )

    if payload.duration_days <= 0:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "duration_days must be a positive integer greater than 0.",
                }
            },
        )

    # Validate that all failed suppliers exist in database
    for fid in payload.failed_supplier_ids:
        sup = db.query(Supplier).filter(Supplier.id == fid).first()
        if not sup:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Supplier with ID {fid} does not exist.",
                    }
                },
            )

    # Convert request mitigations into engine MitigationInput dataclasses
    engine_mitigations: List[MitigationInput] = []
    for mit in payload.mitigations:
        engine_mitigations.append(
            MitigationInput(
                type=mit.type,
                material_id=mit.material_id,
                supplier_id=mit.supplier_id,
                from_supplier_id=mit.from_supplier_id,
                to_supplier_id=mit.to_supplier_id,
                extra_days=mit.extra_days,
                share_pct=mit.share_pct,
                lead_time_reduction_days=mit.lead_time_reduction_days,
            )
        )

    engine = SimulationEngine()
    try:
        sim_result: SimulationResult = engine.run_simulation(
            failed_supplier_ids=payload.failed_supplier_ids,
            duration_days=payload.duration_days,
            mitigations=engine_mitigations,
            scenario_name=payload.name,
            save=payload.save,
            db=db,
            graph_service=graph_service,
        )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                }
            },
        )

    return SimulationResponse(
        scenario_id=sim_result.scenario_id,
        name=sim_result.name,
        failed_supplier_ids=sim_result.failed_supplier_ids,
        duration_days=sim_result.duration_days,
        before_mitigation=_build_outcome_schema(sim_result.before_mitigation),
        after_mitigation=_build_outcome_schema(sim_result.after_mitigation),
        improvement=SimulationImprovementSchema(
            revenue_protected=sim_result.improvement.revenue_protected,
            lines_protected=sim_result.improvement.lines_protected,
        ),
        notes=sim_result.notes,
    )


# =============================================================================
# 2. GET /scenarios — List Saved Scenarios
# =============================================================================

@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    Lists previously saved what-if disruption scenarios with basic metadata.
    """
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0

    total = db.query(Scenario).count()
    scenarios = (
        db.query(Scenario)
        .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        .offset(actual_offset)
        .limit(actual_limit)
        .all()
    )

    items = [
        ScenarioListItem(
            id=s.id,
            name=s.name,
            duration_days=s.duration_days,
            created_at=s.created_at,
        )
        for s in scenarios
    ]

    return ScenarioListResponse(
        items=items,
        total=total,
        limit=actual_limit,
        offset=actual_offset,
    )


# =============================================================================
# 3. GET /scenarios/{id} — Retrieve Scenario Definition & Results
# =============================================================================

@router.get("/scenarios/{id}", response_model=ScenarioDetailResponse)
def get_scenario_detail(
    id: int = Path(..., description="Unique scenario ID", ge=1),
    db: Session = Depends(get_db),
):
    """
    Retrieves the scenario configuration and its persisted before-mitigation
    and after-mitigation impact outcomes.
    """
    scenario = db.query(Scenario).filter(Scenario.id == id).first()
    if not scenario:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Scenario with ID {id} not found.",
                }
            },
        )

    # Fetch stored before and after results
    results = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == id).all()
    res_before = next((r for r in results if r.variant == "before_mitigation"), None)
    res_after = next((r for r in results if r.variant == "after_mitigation"), None)

    if res_before and res_after:
        before_lines = [
            SimulationLineBreakdownSchema(
                line_id=l["line_id"],
                line_name=l["line_name"],
                daily_revenue=l["daily_revenue"],
                days_to_impact=l.get("days_to_impact"),
                unbuffered_days=l["unbuffered_days"],
                revenue_at_risk=l["revenue_at_risk"],
            )
            for l in (res_before.result_detail or {}).get("lines", [])
        ]
        before_schema = SimulationOutcomeSchema(
            lines_at_risk=res_before.lines_at_risk or 0,
            revenue_at_risk=res_before.revenue_at_risk or 0.0,
            days_to_impact=res_before.days_to_impact,
            affected_path=res_before.affected_path or [],
            lines=before_lines,
        )

        after_lines = [
            SimulationLineBreakdownSchema(
                line_id=l["line_id"],
                line_name=l["line_name"],
                daily_revenue=l["daily_revenue"],
                days_to_impact=l.get("days_to_impact"),
                unbuffered_days=l["unbuffered_days"],
                revenue_at_risk=l["revenue_at_risk"],
            )
            for l in (res_after.result_detail or {}).get("lines", [])
        ]
        after_schema = SimulationOutcomeSchema(
            lines_at_risk=res_after.lines_at_risk or 0,
            revenue_at_risk=res_after.revenue_at_risk or 0.0,
            days_to_impact=res_after.days_to_impact,
            affected_path=res_after.affected_path or [],
            lines=after_lines,
        )

        rev_protected = max(0.0, before_schema.revenue_at_risk - after_schema.revenue_at_risk)
        lines_protected = max(0, before_schema.lines_at_risk - after_schema.lines_at_risk)
        notes = [f"Persisted scenario record #{scenario.id}."]
    else:
        # Fallback: recompute on the fly if results were not persisted
        engine = SimulationEngine()
        engine_mitigations = [
            MitigationInput(
                type=m.get("type"),
                material_id=m.get("material_id"),
                supplier_id=m.get("supplier_id"),
                from_supplier_id=m.get("from_supplier_id"),
                to_supplier_id=m.get("to_supplier_id"),
                extra_days=m.get("extra_days"),
                share_pct=m.get("share_pct"),
                lead_time_reduction_days=m.get("lead_time_reduction_days"),
            )
            for m in (scenario.mitigations or [])
        ]
        recomputed = engine.run_simulation(
            failed_supplier_ids=scenario.failed_supplier_ids,
            duration_days=scenario.duration_days,
            mitigations=engine_mitigations,
            scenario_name=scenario.name,
            save=False,
            db=db,
            graph_service=graph_service,
        )
        before_schema = _build_outcome_schema(recomputed.before_mitigation)
        after_schema = _build_outcome_schema(recomputed.after_mitigation)
        rev_protected = recomputed.improvement.revenue_protected
        lines_protected = recomputed.improvement.lines_protected
        notes = recomputed.notes

    return ScenarioDetailResponse(
        id=scenario.id,
        scenario_id=scenario.id,
        name=scenario.name,
        failed_supplier_ids=scenario.failed_supplier_ids,
        duration_days=scenario.duration_days,
        mitigations=scenario.mitigations or [],
        created_at=scenario.created_at,
        before_mitigation=before_schema,
        after_mitigation=after_schema,
        improvement=SimulationImprovementSchema(
            revenue_protected=rev_protected,
            lines_protected=lines_protected,
        ),
        notes=notes,
    )


# =============================================================================
# 4. GET /alternatives/{supplier_id} — Ranked Alternative Suppliers
# =============================================================================

@router.get("/alternatives/{supplier_id}", response_model=AlternativesResponse)
def get_alternative_suppliers(
    supplier_id: int = Path(..., description="Target failed supplier ID", ge=1),
    material_id: Optional[int] = Query(None, description="Optional material ID filter"),
    limit: int = Query(5, ge=1, le=50, description="Maximum recommendations to return"),
    db: Session = Depends(get_db),
):
    """
    Recommends ranked alternative suppliers capable of providing the materials
    disrupted by the target supplier's failure.
    Evaluates qualification, lead time, capacity availability, regional risk,
    and enterprise network familiarity.
    """
    actual_material_id = material_id if isinstance(material_id, int) else None
    actual_limit = limit if isinstance(limit, int) else 5

    target_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not target_supplier:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Supplier with ID {supplier_id} does not exist.",
                }
            },
        )

    material_obj = None
    if actual_material_id is not None:
        material_obj = db.query(Material).filter(Material.id == actual_material_id).first()
        if not material_obj:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Material with ID {actual_material_id} does not exist.",
                    }
                },
            )
    else:
        # Determine primary material provided by target supplier
        sm_first = (
            db.query(SupplierMaterial, Material)
            .join(Material, SupplierMaterial.material_id == Material.id)
            .filter(SupplierMaterial.supplier_id == supplier_id)
            .first()
        )
        if sm_first:
            material_obj = sm_first[1]
        else:
            rel_first = (
                db.query(Relationship, Material)
                .join(Material, Relationship.material_id == Material.id)
                .filter(Relationship.supplier_id == supplier_id)
                .first()
            )
            if rel_first:
                material_obj = rel_first[1]

    engine = SimulationEngine()
    recs = engine.recommend_alternatives(
        supplier_id=supplier_id,
        material_id=actual_material_id,
        limit=actual_limit,
        db=db,
    )

    alt_items: List[AlternativeItem] = []
    for r in recs:
        alt_items.append(
            AlternativeItem(
                supplier=AlternativeSupplierBrief(id=r.supplier_id, name=r.supplier_name),
                rank=r.rank,
                score=r.score,
                lead_time_days=r.lead_time_days,
                capacity_per_month=r.capacity_per_month,
                region_risk=r.region_risk,
                qualified=r.qualified,
                existing_relationship=r.existing_relationship,
                reasons=r.reasons,
            )
        )

    mat_brief = (
        AlternativeMaterialBrief(id=material_obj.id, name=material_obj.name)
        if material_obj
        else None
    )

    return AlternativesResponse(
        failed_supplier=AlternativeSupplierBrief(id=target_supplier.id, name=target_supplier.name),
        material=mat_brief,
        alternatives=alt_items,
    )
