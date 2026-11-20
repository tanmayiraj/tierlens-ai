from typing import Optional, List, Set, Dict, Union
from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db import (
    Supplier,
    SupplierAlias,
    SupplierMaterial,
    Relationship,
    Material,
    DisruptionEvent,
    Alert,
)
from backend.models.schemas import (
    SupplierListItem,
    SupplierListResponse,
    SupplierDetailResponse,
    SupplierDetailSupplied,
    SupplierDetailMaterial,
)

router = APIRouter(tags=["Suppliers"])


@router.get("/suppliers", response_model=SupplierListResponse)
def list_suppliers(
    limit: int = Query(default=50, ge=1, le=200, description="Page limit (1-200)"),
    offset: int = Query(default=0, ge=0, description="Page offset (>= 0)"),
    q: Optional[str] = Query(default=None, description="Case-insensitive supplier name search"),
    region: Optional[str] = Query(default=None, description="Case-insensitive exact region match"),
    tier: Optional[int] = Query(default=None, ge=1, description="Supplier tier filter (>= 1)"),
    min_risk: Optional[float] = Query(default=None, ge=0.0, le=100.0, description="Minimum risk score (0-100)"),
    db: Session = Depends(get_db),
) -> SupplierListResponse:
    """
    List suppliers with pagination, text search, and filtering by region, tier, and risk score.
    Conforms to API_SPEC.md Section 4.4 and Section 1.2.
    """
    # Normalize parameters when called directly as a Python function vs via FastAPI
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0
    actual_q = q if isinstance(q, str) and q.strip() else None
    actual_region = region if isinstance(region, str) and region.strip() else None
    actual_tier = tier if isinstance(tier, int) else None
    actual_min_risk = float(min_risk) if isinstance(min_risk, (int, float)) else None

    # 1. Base query: active suppliers only
    query = db.query(Supplier).filter(Supplier.is_active == True)

    # 2. Case-insensitive substring search on name
    if actual_q is not None:
        query = query.filter(Supplier.name.ilike(f"%{actual_q.strip()}%"))

    # 3. Case-insensitive exact match on region
    if actual_region is not None:
        query = query.filter(func.lower(Supplier.region) == func.lower(actual_region.strip()))

    candidate_suppliers = query.order_by(Supplier.id.asc()).all()

    if not candidate_suppliers:
        return SupplierListResponse(items=[], total=0, limit=actual_limit, offset=actual_offset)

    candidate_ids = [s.id for s in candidate_suppliers]

    # 4. Outgoing supply relationships (status == 'approved') for candidate suppliers
    outgoing_rels = (
        db.query(Relationship.supplier_id, Relationship.tier, Material.name)
        .join(Material, Relationship.material_id == Material.id)
        .filter(
            Relationship.supplier_id.in_(candidate_ids),
            Relationship.status == "approved",
        )
        .all()
    )

    rel_materials: Dict[int, Set[str]] = {}
    rel_tiers: Dict[int, List[int]] = {}
    for sup_id, rel_tier, mat_name in outgoing_rels:
        rel_materials.setdefault(sup_id, set()).add(mat_name)
        if rel_tier is not None:
            rel_tiers.setdefault(sup_id, []).append(rel_tier)

    # 5. Registered supplier capabilities from supplier_materials
    registered_materials = (
        db.query(SupplierMaterial.supplier_id, Material.name)
        .join(Material, SupplierMaterial.material_id == Material.id)
        .filter(SupplierMaterial.supplier_id.in_(candidate_ids))
        .all()
    )

    capability_materials: Dict[int, Set[str]] = {}
    for sup_id, mat_name in registered_materials:
        capability_materials.setdefault(sup_id, set()).add(mat_name)

    # 6. Latest alert risk score per supplier (from DisruptionEvent -> Alert)
    supplier_alerts = (
        db.query(DisruptionEvent.supplier_id, Alert.risk_score)
        .join(Alert, Alert.event_id == DisruptionEvent.id)
        .filter(DisruptionEvent.supplier_id.in_(candidate_ids))
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .all()
    )

    latest_alert_score: Dict[int, float] = {}
    for sup_id, risk_score in supplier_alerts:
        if sup_id not in latest_alert_score:
            latest_alert_score[sup_id] = float(risk_score)

    # 7. Assemble items and apply tier and min_risk filters
    matching_items: List[SupplierListItem] = []
    for s in candidate_suppliers:
        # Minimum computed tier among active outgoing relationships (or None)
        tiers = rel_tiers.get(s.id, [])
        min_tier = min(tiers) if tiers else None

        # Filter by tier if specified
        if actual_tier is not None:
            if min_tier is None or min_tier != actual_tier:
                continue

        # Effective risk score: latest alert if present, else base_risk
        if s.id in latest_alert_score:
            effective_risk = latest_alert_score[s.id]
        else:
            effective_risk = float(s.base_risk) if s.base_risk is not None else 0.0

        # Filter by min_risk if specified
        if actual_min_risk is not None:
            if effective_risk < actual_min_risk:
                continue

        # Aggregate unique materials from capabilities and active outgoing relationships
        combined_materials = rel_materials.get(s.id, set()) | capability_materials.get(s.id, set())
        sorted_materials = sorted(combined_materials)

        item = SupplierListItem(
            id=s.id,
            name=s.name,
            country=s.country,
            region=s.region,
            tier=min_tier,
            risk_score=round(effective_risk, 1) if effective_risk is not None else None,
            materials=sorted_materials,
        )
        matching_items.append(item)

    # 8. Pagination calculation
    total = len(matching_items)
    paginated_items = matching_items[actual_offset : actual_offset + actual_limit]

    return SupplierListResponse(
        items=paginated_items,
        total=total,
        limit=actual_limit,
        offset=actual_offset,
    )


@router.get("/suppliers/{supplier_id}", response_model=SupplierDetailResponse)
def get_supplier(
    supplier_id: int = Path(..., ge=1, description="Unique supplier identifier (>= 1)"),
    db: Session = Depends(get_db),
) -> Union[SupplierDetailResponse, JSONResponse]:
    """
    Retrieve supplier details by ID including aliases, materials, qualification,
    and upstream/downstream relationships.
    Conforms to API_SPEC.md Section 4.4.
    """
    # Validation guard for direct programmatic invocations
    if isinstance(supplier_id, int) and supplier_id < 1:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field-level validation failed.",
                    "details": {"supplier_id": "Must be >= 1"},
                }
            },
        )

    # 1. Fetch active supplier
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier or not supplier.is_active:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Supplier {supplier_id} does not exist.",
                    "details": {},
                }
            },
        )

    # 2. Aliases sorted alphabetically
    aliases_data = (
        db.query(SupplierAlias.alias)
        .filter(SupplierAlias.supplier_id == supplier.id)
        .order_by(SupplierAlias.alias.asc())
        .all()
    )
    aliases = [a[0] for a in aliases_data]

    # 3. Registered materials with qualification status sorted alphabetically by material name
    materials_data = (
        db.query(Material.id, Material.name, SupplierMaterial.is_qualified)
        .select_from(SupplierMaterial)
        .join(Material, SupplierMaterial.material_id == Material.id)
        .filter(SupplierMaterial.supplier_id == supplier.id)
        .order_by(Material.name.asc())
        .all()
    )
    materials = [
        SupplierDetailMaterial(id=m_id, name=m_name, qualified=bool(is_qual))
        for m_id, m_name, is_qual in materials_data
    ]

    # 4. Approved downstream supply relationships (supplies_to)
    supplies_to_data = (
        db.query(Supplier.id, Supplier.name, Material.name, Relationship.tier)
        .select_from(Relationship)
        .join(Supplier, Relationship.buyer_id == Supplier.id)
        .join(Material, Relationship.material_id == Material.id)
        .filter(
            Relationship.supplier_id == supplier.id,
            Relationship.status == "approved",
        )
        .order_by(Supplier.name.asc())
        .all()
    )
    supplies_to = [
        SupplierDetailSupplied(id=b_id, name=b_name, material=m_name)
        for b_id, b_name, m_name, _ in supplies_to_data
    ]

    # 5. Approved upstream supply relationships (supplied_by)
    supplied_by_data = (
        db.query(Supplier.id, Supplier.name, Material.name)
        .select_from(Relationship)
        .join(Supplier, Relationship.supplier_id == Supplier.id)
        .join(Material, Relationship.material_id == Material.id)
        .filter(
            Relationship.buyer_id == supplier.id,
            Relationship.status == "approved",
        )
        .order_by(Supplier.name.asc())
        .all()
    )
    supplied_by = [
        SupplierDetailSupplied(id=s_id, name=s_name, material=m_name)
        for s_id, s_name, m_name in supplied_by_data
    ]

    # 6. Minimum non-null tier among active outgoing relationships (or None)
    outgoing_tiers = [r[3] for r in supplies_to_data if r[3] is not None]
    min_tier = min(outgoing_tiers) if outgoing_tiers else None

    return SupplierDetailResponse(
        id=supplier.id,
        name=supplier.name,
        aliases=aliases,
        country=supplier.country,
        region=supplier.region,
        capacity_per_month=supplier.capacity_per_month,
        base_risk=float(supplier.base_risk) if supplier.base_risk is not None else 0.0,
        tier=min_tier,
        supplies_to=supplies_to,
        supplied_by=supplied_by,
        materials=materials,
    )
