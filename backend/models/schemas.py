from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentBase(BaseModel):
    filename: str
    doc_type: str
    file_path: str
    raw_text: Optional[str] = None
    page_count: Optional[int] = None
    extraction_status: Literal["pending", "processing", "done", "failed"] = "pending"


class DocumentRead(DocumentBase):
    id: int
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierBase(BaseModel):
    name: str
    entity_type: Literal["manufacturer", "supplier"] = "supplier"
    country: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity_per_month: Optional[float] = None
    base_risk: float = Field(default=0.0, ge=0, le=100)
    is_active: bool = True


class SupplierRead(SupplierBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierListItem(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    region: Optional[str] = None
    tier: Optional[int] = None
    risk_score: Optional[float] = None
    materials: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class SupplierListResponse(BaseModel):
    items: List[SupplierListItem] = Field(default_factory=list)
    total: int
    limit: int = 50
    offset: int = 0
    model_config = ConfigDict(from_attributes=True)


class SupplierDetailSupplied(BaseModel):
    id: int
    name: str
    material: str
    model_config = ConfigDict(from_attributes=True)


class SupplierDetailMaterial(BaseModel):
    id: int
    name: str
    qualified: bool = False
    model_config = ConfigDict(from_attributes=True)


class SupplierDetailResponse(BaseModel):
    id: int
    name: str
    aliases: List[str] = Field(default_factory=list)
    country: Optional[str] = None
    region: Optional[str] = None
    capacity_per_month: Optional[float] = None
    base_risk: float = 0.0
    tier: Optional[int] = None
    supplies_to: List[SupplierDetailSupplied] = Field(default_factory=list)
    supplied_by: List[SupplierDetailSupplied] = Field(default_factory=list)
    materials: List[SupplierDetailMaterial] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class SupplierAliasBase(BaseModel):
    supplier_id: int
    alias: str
    match_score: Optional[float] = None
    resolved_by: Optional[str] = None


class SupplierAliasRead(SupplierAliasBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MaterialBase(BaseModel):
    name: str
    material_type: Literal["raw", "part", "assembly"]
    unit: Optional[str] = None
    category: Optional[str] = None


class MaterialRead(MaterialBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SupplierMaterialBase(BaseModel):
    supplier_id: int
    material_id: int
    capacity_per_month: Optional[float] = None
    typical_lead_time_days: Optional[int] = None
    is_qualified: bool = False


class SupplierMaterialRead(SupplierMaterialBase):
    model_config = ConfigDict(from_attributes=True)


class EvidenceBase(BaseModel):
    document_id: int
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    snippet: str
    llm_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class EvidenceRead(EvidenceBase):
    id: int
    extracted_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RelationshipBase(BaseModel):
    supplier_id: int
    buyer_id: int
    material_id: int
    tier: Optional[int] = Field(default=None, ge=1)
    lead_time_days: Optional[int] = None
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    inventory_days: int = 0
    quantity_per_month: Optional[float] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    status: Literal["pending", "approved", "rejected"] = "pending"
    evidence_id: Optional[int] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class RelationshipRead(RelationshipBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RelationshipEvidenceRead(BaseModel):
    relationship_id: int
    evidence_id: int
    model_config = ConfigDict(from_attributes=True)


class RelationshipPartyRef(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class RelationshipMaterialRef(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class RelationshipListItem(BaseModel):
    id: int
    supplier: RelationshipPartyRef
    buyer: RelationshipPartyRef
    material: RelationshipMaterialRef
    tier: Optional[int] = None
    lead_time_days: Optional[int] = None
    share_pct: Optional[float] = None
    inventory_days: int = 0
    confidence: Optional[float] = None
    status: Literal["pending", "approved", "rejected"] = "pending"
    evidence_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class RelationshipListResponse(BaseModel):
    items: List[RelationshipListItem] = Field(default_factory=list)
    total: int
    limit: int = 50
    offset: int = 0
    model_config = ConfigDict(from_attributes=True)


class ReviewQueueItem(BaseModel):
    relationship_id: int
    supplier: str
    buyer: str
    material: str
    confidence: Optional[float] = None
    snippet: Optional[str] = None
    document: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItem] = Field(default_factory=list)
    total: int
    model_config = ConfigDict(from_attributes=True)


class ReviewCorrections(BaseModel):
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    lead_time_days: Optional[int] = Field(default=None, ge=0)
    model_config = ConfigDict(extra="forbid")


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    corrections: Optional[ReviewCorrections] = None
    reviewed_by: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    status: Literal["approved", "rejected"]
    graph_rebuild_required: bool = True
    model_config = ConfigDict(from_attributes=True)


class PlantBase(BaseModel):
    manufacturer_id: int
    name: str
    location: Optional[str] = None


class PlantRead(PlantBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    unit_revenue: Optional[float] = None


class ProductRead(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductionLineBase(BaseModel):
    plant_id: int
    product_id: int
    name: str
    units_per_day: float
    daily_revenue: Optional[float] = None


class ProductionLineRead(ProductionLineBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class LineRequirementBase(BaseModel):
    line_id: int
    material_id: int
    qty_per_day: float
    criticality: Literal["high", "medium", "low"] = "high"
    safety_stock_days: int = 0


class LineRequirementRead(LineRequirementBase):
    model_config = ConfigDict(from_attributes=True)


class DisruptionEventBase(BaseModel):
    supplier_id: int
    event_type: Literal["shutdown", "delay", "shortage", "transport", "natural_disaster", "quality"]
    severity: int = Field(ge=1, le=5)
    start_date: date
    expected_duration_days: Optional[int] = None
    description: Optional[str] = None
    source: Optional[str] = None
    is_simulated: bool = True


class DisruptionEventRead(DisruptionEventBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertBase(BaseModel):
    event_id: int
    severity_label: Literal["low", "medium", "high", "critical"]
    risk_score: float = Field(ge=0, le=100)
    score_breakdown: Dict[str, Any]
    days_to_impact: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    explanation: Optional[str] = None
    status: Literal["open", "investigating", "acknowledged", "resolved"] = "open"


class AlertRead(AlertBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertAffectedNodeBase(BaseModel):
    alert_id: int
    node_type: Literal["supplier", "material", "line", "product"]
    node_id: int
    path_depth: Optional[int] = None
    days_to_impact: Optional[int] = None


class AlertAffectedNodeRead(AlertAffectedNodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ScenarioBase(BaseModel):
    name: str
    failed_supplier_ids: List[int]
    duration_days: int
    mitigations: Optional[List[Dict[str, Any]]] = None


class ScenarioRead(ScenarioBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScenarioResultBase(BaseModel):
    scenario_id: int
    variant: Literal["before_mitigation", "after_mitigation"]
    lines_at_risk: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    days_to_impact: Optional[int] = None
    affected_path: Optional[List[Any]] = None
    result_detail: Optional[Dict[str, Any]] = None


class ScenarioResultRead(ScenarioResultBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Graph & Dependency Schemas (TASK-010)
# =============================================================================

class GraphNodeItem(BaseModel):
    id: str
    type: Literal["supplier", "line"]
    label: str
    tier: Optional[int] = None
    region: Optional[str] = None
    risk_score: float = 0.0
    flags: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class GraphEdgeItem(BaseModel):
    id: str
    source: str
    target: str
    material: str
    lead_time_days: Optional[int] = None
    share_pct: Optional[float] = None
    confidence: Optional[float] = None
    status: Literal["approved", "pending"] = "approved"
    model_config = ConfigDict(from_attributes=True)


class GraphMeta(BaseModel):
    built_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GraphResponse(BaseModel):
    nodes: List[GraphNodeItem] = Field(default_factory=list)
    edges: List[GraphEdgeItem] = Field(default_factory=list)
    meta: GraphMeta = Field(default_factory=GraphMeta)
    model_config = ConfigDict(from_attributes=True)


class GraphRebuildResponse(BaseModel):
    nodes: int
    edges: int
    max_tier: int
    built_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NodeReaches(BaseModel):
    tier1_suppliers: List[str] = Field(default_factory=list)
    production_lines: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class NodeNeighborRef(BaseModel):
    id: str
    label: str
    material: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NodeEvidenceItem(BaseModel):
    document: str
    page: Optional[int] = None
    snippet: str
    confidence: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class NodeDetailResponse(BaseModel):
    id: str
    type: Literal["supplier", "line"]
    label: str
    tier: Optional[int] = None
    risk_score: float = 0.0
    risk_breakdown: Dict[str, Any] = Field(default_factory=dict)
    upstream: List[NodeNeighborRef] = Field(default_factory=list)
    downstream: List[NodeNeighborRef] = Field(default_factory=list)
    reaches: NodeReaches = Field(default_factory=NodeReaches)
    evidence: List[NodeEvidenceItem] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class DependencySupplierRef(BaseModel):
    id: int
    name: str
    tier: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class DependencyMaterialRef(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class DependencyItem(BaseModel):
    id: str
    type: Literal["shared_upstream_supplier", "single_source_material"]
    supplier: Optional[DependencySupplierRef] = None
    material: Optional[DependencyMaterialRef] = None
    description: str
    affected_tier1: Optional[List[str]] = None
    affected_lines: Optional[List[str]] = None
    severity: Literal["low", "medium", "high", "critical"] = "high"
    model_config = ConfigDict(from_attributes=True)


class DependencyResponse(BaseModel):
    items: List[DependencyItem] = Field(default_factory=list)
    total: int
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Document & Extraction Schemas (Milestone 4: TASK-021, TASK-022, TASK-023)
# =============================================================================

class DocumentUploadItem(BaseModel):
    id: int
    filename: str
    extraction_status: Literal["pending", "processing", "done", "failed"] = "pending"
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    documents: List[DocumentUploadItem] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class LoadSamplesResponse(BaseModel):
    loaded: int
    queued_for_extraction: int
    model_config = ConfigDict(from_attributes=True)


class DocumentListItem(BaseModel):
    id: int
    filename: str
    doc_type: str
    extraction_status: Literal["pending", "processing", "done", "failed"]
    uploaded_at: datetime
    relationships_found: int = 0
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: List[DocumentListItem] = Field(default_factory=list)
    total: int
    limit: int = 50
    offset: int = 0
    model_config = ConfigDict(from_attributes=True)


class DocumentStats(BaseModel):
    entities: int = 0
    relationships: int = 0
    low_confidence: int = 0
    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    id: int
    filename: str
    doc_type: str
    page_count: Optional[int] = None
    extraction_status: Literal["pending", "processing", "done", "failed"]
    uploaded_at: datetime
    stats: DocumentStats = Field(default_factory=DocumentStats)
    model_config = ConfigDict(from_attributes=True)


class DocumentEvidenceRelationshipRef(BaseModel):
    id: int
    supplier: str
    buyer: str
    material: str
    model_config = ConfigDict(from_attributes=True)


class DocumentEvidenceItem(BaseModel):
    id: int
    page: Optional[int] = None
    snippet: str
    llm_confidence: Optional[float] = None
    relationship: Optional[DocumentEvidenceRelationshipRef] = None
    model_config = ConfigDict(from_attributes=True)


class DocumentEvidenceResponse(BaseModel):
    document_id: int
    evidence: List[DocumentEvidenceItem] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ExtractionRelationshipItem(BaseModel):
    supplier: str
    buyer: str
    material: str
    lead_time_days: Optional[int] = None
    share_pct: Optional[float] = None
    quantity_per_month: Optional[float] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_doc: Optional[str] = None
    snippet: str
    page: Optional[int] = 1
    model_config = ConfigDict(from_attributes=True)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v: Any) -> float:
        if v is None:
            return 0.8
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Confidence must be a numeric value, got {v}")
        if 0.0 <= val <= 1.0:
            return val
        if 1.0 < val <= 100.0:
            return val / 100.0
        raise ValueError(f"Confidence {val} is invalid (must be between 0 and 100)")


class ExtractionResult(BaseModel):
    relationships: List[ExtractionRelationshipItem] = Field(default_factory=list)
    entities_found: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Risk Analysis & Disruption Event Schemas (TASK-017)
# =============================================================================

class EventCreateRequest(BaseModel):
    supplier_id: int
    event_type: Literal["shutdown", "delay", "shortage", "transport", "natural_disaster", "quality"]
    severity: int = Field(ge=1, le=5)
    start_date: date
    expected_duration_days: Optional[int] = Field(default=None, ge=1)
    description: Optional[str] = None
    source: Optional[str] = "manual"
    is_simulated: bool = False


class EventCreateResponse(BaseModel):
    event_id: int
    alert_id: int
    severity_label: Literal["low", "medium", "high", "critical"]
    risk_score: float
    model_config = ConfigDict(from_attributes=True)


class EventSupplierRef(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class EventListItem(BaseModel):
    id: int
    supplier: EventSupplierRef
    event_type: str
    severity: int
    start_date: date
    expected_duration_days: Optional[int] = None
    description: Optional[str] = None
    source: Optional[str] = None
    is_simulated: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    items: List[EventListItem] = Field(default_factory=list)
    total: int
    limit: int = 50
    offset: int = 0
    model_config = ConfigDict(from_attributes=True)


class AlertListItem(BaseModel):
    id: int
    event_id: int
    supplier: str
    supplier_id: Optional[int] = None
    severity_label: Literal["low", "medium", "high", "critical"]
    risk_score: float
    days_to_impact: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    status: Literal["open", "investigating", "acknowledged", "resolved"]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    items: List[AlertListItem] = Field(default_factory=list)
    total: int
    limit: int = 50
    offset: int = 0
    model_config = ConfigDict(from_attributes=True)


class AlertEventDetail(BaseModel):
    id: int
    supplier: str
    supplier_id: Optional[int] = None
    event_type: str
    expected_duration_days: Optional[int] = None
    start_date: Optional[date] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AlertAffectedNodeItem(BaseModel):
    node_type: Literal["supplier", "line", "material", "product"]
    name: str
    node_id: Optional[int] = None
    path_depth: Optional[int] = None
    days_to_impact: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class AlertEvidenceItem(BaseModel):
    document: str
    page: Optional[int] = None
    snippet: str
    model_config = ConfigDict(from_attributes=True)


class AlertDetailResponse(BaseModel):
    id: int
    event: AlertEventDetail
    severity_label: Literal["low", "medium", "high", "critical"]
    risk_score: float
    score_breakdown: Dict[str, float]
    days_to_impact: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    explanation: Optional[str] = None
    affected: List[AlertAffectedNodeItem] = Field(default_factory=list)
    evidence: List[AlertEvidenceItem] = Field(default_factory=list)
    alternatives_url: Optional[str] = None
    status: Literal["open", "investigating", "acknowledged", "resolved"]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertUpdateStatusRequest(BaseModel):
    status: Literal["open", "investigating", "acknowledged", "resolved"]
    model_config = ConfigDict(extra="forbid")


class AlertUpdateStatusResponse(BaseModel):
    id: int
    status: Literal["open", "investigating", "acknowledged", "resolved"]
    model_config = ConfigDict(from_attributes=True)


class ImpactOrigin(BaseModel):
    id: str
    label: str
    tier: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class ImpactSummary(BaseModel):
    suppliers_affected: int
    materials_affected: int
    lines_affected: int
    products_affected: int
    first_impact_in_days: Optional[int] = None
    revenue_at_risk: float
    model_config = ConfigDict(from_attributes=True)


class ImpactPathItem(BaseModel):
    nodes: List[str]
    days_to_impact: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class ImpactAffectedNode(BaseModel):
    node_type: Literal["supplier", "line", "material", "product"]
    id: int
    name: str
    days_to_impact: Optional[int] = None
    unbuffered_days: Optional[int] = None
    revenue_at_risk: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class ImpactResponse(BaseModel):
    event_id: int
    origin: ImpactOrigin
    summary: ImpactSummary
    paths: List[ImpactPathItem] = Field(default_factory=list)
    affected_nodes: List[ImpactAffectedNode] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class RiskSummaryNetwork(BaseModel):
    suppliers: int
    tier1: int
    tier2: int
    tier3: int
    model_config = ConfigDict(from_attributes=True)


class RiskSummaryOpenAlerts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    model_config = ConfigDict(from_attributes=True)


class TopRiskySupplierItem(BaseModel):
    id: int
    name: str
    tier: Optional[int] = None
    risk_score: float
    model_config = ConfigDict(from_attributes=True)


class RiskSummaryResponse(BaseModel):
    network: RiskSummaryNetwork
    hidden_dependencies: int
    single_source_materials: int
    open_alerts: RiskSummaryOpenAlerts
    top_risky_suppliers: List[TopRiskySupplierItem] = Field(default_factory=list)
    total_revenue_at_risk: float
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Simulation & Scenario Schemas (TASK-025)
# =============================================================================

class MitigationSchema(BaseModel):
    """Mitigation input configuration for what-if simulation."""
    type: Literal["alternate_supplier", "safety_stock", "reroute", "expedite"]
    material_id: Optional[int] = None
    supplier_id: Optional[int] = None
    from_supplier_id: Optional[int] = None
    to_supplier_id: Optional[int] = None
    extra_days: Optional[int] = None
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    lead_time_reduction_days: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class SimulationRequest(BaseModel):
    """Request payload for POST /simulate."""
    name: Optional[str] = None
    failed_supplier_ids: List[int]
    duration_days: int = Field(gt=0)
    mitigations: List[MitigationSchema] = Field(default_factory=list)
    save: bool = False
    model_config = ConfigDict(from_attributes=True)


class SimulationLineBreakdownSchema(BaseModel):
    """Line-by-line downtime and revenue breakdown."""
    line_id: int
    line_name: str
    daily_revenue: float
    days_to_impact: Optional[int] = None
    unbuffered_days: int
    revenue_at_risk: float
    model_config = ConfigDict(from_attributes=True)


class SimulationOutcomeSchema(BaseModel):
    """Operational impact outcome for a simulation variant."""
    lines_at_risk: int
    revenue_at_risk: float
    days_to_impact: Optional[int] = None
    affected_path: List[str] = Field(default_factory=list)
    lines: List[SimulationLineBreakdownSchema] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class SimulationImprovementSchema(BaseModel):
    """Protection delta achieved by active mitigations."""
    revenue_protected: float
    lines_protected: int
    model_config = ConfigDict(from_attributes=True)


class SimulationResponse(BaseModel):
    """Response returned by POST /simulate."""
    scenario_id: Optional[int] = None
    name: Optional[str] = None
    failed_supplier_ids: List[int]
    duration_days: int
    before_mitigation: SimulationOutcomeSchema
    after_mitigation: SimulationOutcomeSchema
    improvement: SimulationImprovementSchema
    notes: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ScenarioListItem(BaseModel):
    """Summary item in GET /scenarios list."""
    id: int
    name: str
    duration_days: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScenarioListResponse(BaseModel):
    """Response returned by GET /scenarios."""
    items: List[ScenarioListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    model_config = ConfigDict(from_attributes=True)


class ScenarioDetailResponse(BaseModel):
    """Response returned by GET /scenarios/{id}."""
    id: int
    scenario_id: int
    name: str
    failed_supplier_ids: List[int]
    duration_days: int
    mitigations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    before_mitigation: SimulationOutcomeSchema
    after_mitigation: SimulationOutcomeSchema
    improvement: SimulationImprovementSchema
    notes: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class AlternativeSupplierBrief(BaseModel):
    """Minimal supplier reference for alternatives."""
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class AlternativeMaterialBrief(BaseModel):
    """Minimal material reference for alternatives."""
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class AlternativeItem(BaseModel):
    """Single ranked alternative recommendation."""
    supplier: AlternativeSupplierBrief
    rank: int
    score: float
    lead_time_days: Optional[int] = None
    capacity_per_month: Optional[float] = None
    region_risk: str
    qualified: bool
    existing_relationship: bool
    reasons: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class AlternativesResponse(BaseModel):
    """Response returned by GET /alternatives/{supplier_id}."""
    failed_supplier: AlternativeSupplierBrief
    material: Optional[AlternativeMaterialBrief] = None
    alternatives: List[AlternativeItem] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)