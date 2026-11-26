from sqlalchemy import (
    Column, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, CheckConstraint, UniqueConstraint, Index, JSON, Text, func, text
)
from sqlalchemy.orm import relationship as orm_relationship
from backend.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(Text, nullable=False)
    doc_type = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    extraction_status = Column(Text, nullable=False, default="pending", server_default="pending")
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('pending', 'processing', 'done', 'failed')",
            name="check_doc_extraction_status"
        ),
    )

    evidence_records = orm_relationship("Evidence", back_populates="document", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    entity_type = Column(Text, nullable=False, default="supplier", server_default="supplier")
    country = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    capacity_per_month = Column(Float, nullable=True)
    base_risk = Column(Float, default=0, server_default=text("0"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('manufacturer', 'supplier')",
            name="check_supplier_entity_type"
        ),
        CheckConstraint(
            "base_risk BETWEEN 0 AND 100",
            name="check_supplier_base_risk"
        ),
    )

    aliases = orm_relationship("SupplierAlias", back_populates="supplier", cascade="all, delete-orphan")
    supplied_materials = orm_relationship("SupplierMaterial", back_populates="supplier")
    plants = orm_relationship("Plant", back_populates="manufacturer")
    events = orm_relationship("DisruptionEvent", back_populates="supplier")


class SupplierAlias(Base):
    __tablename__ = "supplier_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    alias = Column(Text, nullable=False)
    match_score = Column(Float, nullable=True)
    resolved_by = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("supplier_id", "alias", name="uq_supplier_alias"),
        Index("idx_alias_alias", "alias"),
    )

    supplier = orm_relationship("Supplier", back_populates="aliases")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    material_type = Column(Text, nullable=False)
    unit = Column(Text, nullable=True)
    category = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "material_type IN ('raw', 'part', 'assembly')",
            name="check_material_type"
        ),
    )

    supplier_materials = orm_relationship("SupplierMaterial", back_populates="material")


class SupplierMaterial(Base):
    __tablename__ = "supplier_materials"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), primary_key=True, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), primary_key=True, nullable=False)
    capacity_per_month = Column(Float, nullable=True)
    typical_lead_time_days = Column(Integer, nullable=True)
    is_qualified = Column(Boolean, nullable=False, default=False, server_default=text("0"))

    __table_args__ = (
        Index("idx_supmat_material", "material_id"),
    )

    supplier = orm_relationship("Supplier", back_populates="supplied_materials")
    material = orm_relationship("Material", back_populates="supplier_materials")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=True)
    snippet = Column(Text, nullable=False)
    llm_confidence = Column(Float, nullable=True)
    extracted_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "llm_confidence BETWEEN 0 AND 1",
            name="check_evidence_llm_confidence"
        ),
        Index("idx_evidence_doc", "document_id"),
    )

    document = orm_relationship("Document", back_populates="evidence_records")
    relationship_links = orm_relationship("RelationshipEvidence", back_populates="evidence", cascade="all, delete-orphan")


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    tier = Column(Integer, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    share_pct = Column(Float, nullable=True)
    inventory_days = Column(Integer, default=0, server_default=text("0"))
    quantity_per_month = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(Text, nullable=False, default="pending", server_default="pending")
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True)
    reviewed_by = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("supplier_id <> buyer_id", name="check_rel_no_self_supply"),
        CheckConstraint("tier >= 1", name="check_rel_tier_ge_1"),
        CheckConstraint("share_pct BETWEEN 0 AND 100", name="check_rel_share_pct"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="check_rel_confidence"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="check_rel_status"),
        UniqueConstraint("supplier_id", "buyer_id", "material_id", name="uq_supplier_buyer_material"),
        Index("idx_rel_supplier", "supplier_id"),
        Index("idx_rel_buyer", "buyer_id"),
        Index("idx_rel_material", "material_id"),
        Index("idx_rel_status", "status"),
    )

    supplier = orm_relationship("Supplier", foreign_keys=[supplier_id])
    buyer = orm_relationship("Supplier", foreign_keys=[buyer_id])
    material = orm_relationship("Material")
    primary_evidence = orm_relationship("Evidence", foreign_keys=[evidence_id])
    evidence_links = orm_relationship("RelationshipEvidence", back_populates="relationship", cascade="all, delete-orphan")


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"

    relationship_id = Column(Integer, ForeignKey("relationships.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True, nullable=False)

    relationship = orm_relationship("Relationship", back_populates="evidence_links")
    evidence = orm_relationship("Evidence", back_populates="relationship_links")


class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    manufacturer_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    name = Column(Text, nullable=False)
    location = Column(Text, nullable=True)

    manufacturer = orm_relationship("Supplier", back_populates="plants")
    production_lines = orm_relationship("ProductionLine", back_populates="plant")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    unit_revenue = Column(Float, nullable=True)

    production_lines = orm_relationship("ProductionLine", back_populates="product")


class ProductionLine(Base):
    __tablename__ = "production_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(Text, nullable=False)
    units_per_day = Column(Float, nullable=False)
    daily_revenue = Column(Float, nullable=True)

    plant = orm_relationship("Plant", back_populates="production_lines")
    product = orm_relationship("Product", back_populates="production_lines")
    requirements = orm_relationship("LineRequirement", back_populates="production_line", cascade="all, delete-orphan")


class LineRequirement(Base):
    __tablename__ = "line_requirements"

    line_id = Column(Integer, ForeignKey("production_lines.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), primary_key=True, nullable=False)
    qty_per_day = Column(Float, nullable=False)
    criticality = Column(Text, nullable=False, default="high", server_default="high")
    safety_stock_days = Column(Integer, default=0, server_default=text("0"))

    __table_args__ = (
        CheckConstraint("criticality IN ('high', 'medium', 'low')", name="check_line_req_criticality"),
    )

    production_line = orm_relationship("ProductionLine", back_populates="requirements")
    material = orm_relationship("Material")


class DisruptionEvent(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    severity = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    expected_duration_days = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    is_simulated = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('shutdown', 'delay', 'shortage', 'transport', 'natural_disaster', 'quality')",
            name="check_event_type"
        ),
        CheckConstraint("severity BETWEEN 1 AND 5", name="check_event_severity"),
        Index("idx_events_supplier", "supplier_id"),
    )

    supplier = orm_relationship("Supplier", back_populates="events")
    alerts = orm_relationship("Alert", back_populates="event", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    severity_label = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, nullable=False)
    days_to_impact = Column(Integer, nullable=True)
    revenue_at_risk = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="open", server_default="open")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity_label IN ('low', 'medium', 'high', 'critical')", name="check_alert_severity_label"),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="check_alert_risk_score"),
        CheckConstraint("status IN ('open', 'investigating', 'acknowledged', 'resolved')", name="check_alert_status"),
        Index("idx_alerts_event", "event_id"),
        Index("idx_alerts_status", "status", "risk_score"),
    )

    event = orm_relationship("DisruptionEvent", back_populates="alerts")
    affected_nodes = orm_relationship("AlertAffectedNode", back_populates="alert", cascade="all, delete-orphan")


class AlertAffectedNode(Base):
    __tablename__ = "alert_affected_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(Text, nullable=False)
    node_id = Column(Integer, nullable=False)
    path_depth = Column(Integer, nullable=True)
    days_to_impact = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("node_type IN ('supplier', 'material', 'line', 'product')", name="check_affected_node_type"),
        Index("idx_affected_alert", "alert_id"),
    )

    alert = orm_relationship("Alert", back_populates="affected_nodes")


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    failed_supplier_ids = Column(JSON, nullable=False)
    duration_days = Column(Integer, nullable=False)
    mitigations = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    results = orm_relationship("ScenarioResult", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False)
    variant = Column(Text, nullable=False)
    lines_at_risk = Column(Integer, nullable=True)
    revenue_at_risk = Column(Float, nullable=True)
    days_to_impact = Column(Integer, nullable=True)
    affected_path = Column(JSON, nullable=True)
    result_detail = Column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint("variant IN ('before_mitigation', 'after_mitigation')", name="check_scenario_variant"),
    )

    scenario = orm_relationship("Scenario", back_populates="results")

