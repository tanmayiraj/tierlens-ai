from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


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
    status: Literal["open", "acknowledged", "resolved"] = "open"


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
