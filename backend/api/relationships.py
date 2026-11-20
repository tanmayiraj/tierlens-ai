from typing import Optional, List, Dict, Union
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db import (
    Relationship,
    RelationshipEvidence,
)
from backend.models.schemas import (
    RelationshipPartyRef,
    RelationshipMaterialRef,
    RelationshipListItem,
    RelationshipListResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
    ReviewRequest,
    ReviewResponse,
)

router = APIRouter(tags=["Relationships"])


@router.get("/relationships", response_model=RelationshipListResponse)
def list_relationships(
    status: Optional[str] = Query(default=None, description="Filter by status ('pending', 'approved', 'rejected')"),
    tier: Optional[int] = Query(default=None, ge=1, description="Filter by tier (>= 1)"),
    material_id: Optional[int] = Query(default=None, ge=1, description="Filter by material ID"),
    supplier_id: Optional[int] = Query(default=None, ge=1, description="Filter by supplier ID"),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Filter by minimum confidence (0-1)"),
    limit: int = Query(default=50, ge=1, le=200, description="Page limit (1-200)"),
    offset: int = Query(default=0, ge=0, description="Page offset (>= 0)"),
    db: Session = Depends(get_db),
) -> RelationshipListResponse:
    """
    List supplier relationships with filtering by status, tier, material, supplier, and confidence.
    Conforms to API_SPEC.md Section 4.3.
    """
    # Normalize parameters for direct programmatic invocations
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0
    actual_status = status if isinstance(status, str) and status.strip() else None
    actual_tier = tier if isinstance(tier, int) else None
    actual_material_id = material_id if isinstance(material_id, int) else None
    actual_supplier_id = supplier_id if isinstance(supplier_id, int) else None
    actual_min_confidence = float(min_confidence) if isinstance(min_confidence, (int, float)) else None

    query = db.query(Relationship)

    if actual_status is not None:
        query = query.filter(Relationship.status == actual_status)
    if actual_tier is not None:
        query = query.filter(Relationship.tier == actual_tier)
    if actual_material_id is not None:
        query = query.filter(Relationship.material_id == actual_material_id)
    if actual_supplier_id is not None:
        query = query.filter(Relationship.supplier_id == actual_supplier_id)
    if actual_min_confidence is not None:
        query = query.filter(Relationship.confidence >= actual_min_confidence)

    total = query.count()

    rels = (
        query.order_by(Relationship.id.asc())
        .offset(actual_offset)
        .limit(actual_limit)
        .all()
    )

    if not rels:
        return RelationshipListResponse(items=[], total=total, limit=actual_limit, offset=actual_offset)

    rel_ids = [r.id for r in rels]

    # Calculate evidence count using relationship_evidence junction table
    evidence_counts: Dict[int, int] = {}
    if rel_ids:
        counts = (
            db.query(RelationshipEvidence.relationship_id, func.count(RelationshipEvidence.evidence_id))
            .filter(RelationshipEvidence.relationship_id.in_(rel_ids))
            .group_by(RelationshipEvidence.relationship_id)
            .all()
        )
        for rid, count in counts:
            evidence_counts[rid] = count

    items: List[RelationshipListItem] = []
    for r in rels:
        ev_count = evidence_counts.get(r.id, 0)
        # Fallback to relationships.evidence_id if junction table has no rows
        if ev_count == 0 and r.evidence_id is not None:
            ev_count = 1

        items.append(
            RelationshipListItem(
                id=r.id,
                supplier=RelationshipPartyRef(id=r.supplier.id, name=r.supplier.name),
                buyer=RelationshipPartyRef(id=r.buyer.id, name=r.buyer.name),
                material=RelationshipMaterialRef(id=r.material.id, name=r.material.name),
                tier=r.tier,
                lead_time_days=r.lead_time_days,
                share_pct=r.share_pct,
                inventory_days=r.inventory_days,
                confidence=r.confidence,
                status=r.status,
                evidence_count=ev_count,
            )
        )

    return RelationshipListResponse(
        items=items,
        total=total,
        limit=actual_limit,
        offset=actual_offset,
    )


@router.get("/review-queue", response_model=ReviewQueueResponse)
def get_review_queue(db: Session = Depends(get_db)) -> ReviewQueueResponse:
    """
    Retrieve pending relationships ordered by confidence ascending.
    Queries the existing review_queue SQL view per DATABASE_SCHEMA.md Section 3.18.
    """
    result = db.execute(
        text("SELECT id, supplier, buyer, material, confidence, snippet, filename FROM review_queue ORDER BY confidence ASC")
    ).fetchall()

    items = [
        ReviewQueueItem(
            relationship_id=row[0],
            supplier=row[1],
            buyer=row[2],
            material=row[3],
            confidence=float(row[4]) if row[4] is not None else None,
            snippet=row[5],
            document=row[6],
        )
        for row in result
    ]

    return ReviewQueueResponse(items=items, total=len(items))


@router.post("/review/{relationship_id}", response_model=ReviewResponse)
def review_relationship(
    relationship_id: int = Path(..., ge=1, description="Relationship ID to review (>= 1)"),
    body: ReviewRequest = ...,
    db: Session = Depends(get_db),
) -> Union[ReviewResponse, JSONResponse]:
    """
    Approve, reject, or correct and approve a relationship.
    Conforms to API_SPEC.md Section 4.3.
    """
    # Programmatic validation guard
    if isinstance(relationship_id, int) and relationship_id < 1:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field-level validation failed.",
                    "details": {"relationship_id": "Must be >= 1"},
                }
            },
        )

    # Reject requests with corrections if action is 'reject'
    if body.action == "reject" and body.corrections is not None:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Corrections cannot be applied when action is reject.",
                    "details": {"corrections": "Must not be provided when rejecting a relationship."},
                }
            },
        )

    rel = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not rel:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Relationship {relationship_id} does not exist.",
                    "details": {},
                }
            },
        )

    # Apply corrections before approval
    if body.action == "approve" and body.corrections is not None:
        corr_dict = body.corrections.model_dump(exclude_unset=True)
        if "share_pct" in corr_dict and corr_dict["share_pct"] is not None:
            rel.share_pct = corr_dict["share_pct"]
        if "lead_time_days" in corr_dict and corr_dict["lead_time_days"] is not None:
            rel.lead_time_days = corr_dict["lead_time_days"]

    # Map request action to database relationship status ('approved' or 'rejected')
    new_status = "approved" if body.action == "approve" else "rejected"
    rel.status = new_status
    rel.reviewed_by = body.reviewed_by
    rel.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(rel)

    return ReviewResponse(
        id=rel.id,
        status=rel.status,
        graph_rebuild_required=True,
    )
