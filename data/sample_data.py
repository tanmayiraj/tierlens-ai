"""
Synthetic automotive demonstration dataset for TierLens AI.
Reference: DATABASE_SCHEMA.md Section 9, API_SPEC.md, and ARCHITECTURE.md.

All records in this dataset are synthetic demonstration data created specifically
to test multi-tier supplier visibility and disruption propagation.
"""

from datetime import date

# 1. Documents (source procurement files)
SAMPLE_DOCUMENTS = [
    {
        "filename": "PO_1042.pdf",
        "doc_type": "purchase_order",
        "file_path": "data/sample_docs/PO_1042.pdf",
        "raw_text": "[DEMONSTRATION SAMPLE] Purchase Order PO_1042: GreenLatex Pvt Ltd to supply 40 MT of natural latex to RubberCore Industries monthly.",
        "page_count": 2,
        "extraction_status": "done",
    },
    {
        "filename": "Contract_RubberCore_TyreWorks.txt",
        "doc_type": "contract",
        "file_path": "data/sample_docs/Contract_RubberCore_TyreWorks.txt",
        "raw_text": "[DEMONSTRATION SAMPLE] Supply Agreement: RubberCore Industries to supply processed rubber compound to TyreWorks Ltd.",
        "page_count": 1,
        "extraction_status": "done",
    },
    {
        "filename": "Contract_RubberCore_GripSeal.txt",
        "doc_type": "contract",
        "file_path": "data/sample_docs/Contract_RubberCore_GripSeal.txt",
        "raw_text": "[DEMONSTRATION SAMPLE] Supply Agreement: RubberCore Industries to supply processed rubber compound to GripSeal Components.",
        "page_count": 1,
        "extraction_status": "done",
    },
    {
        "filename": "PO_TyreWorks_AutoMotive.pdf",
        "doc_type": "purchase_order",
        "file_path": "data/sample_docs/PO_TyreWorks_AutoMotive.pdf",
        "raw_text": "[DEMONSTRATION SAMPLE] Purchase Order: TyreWorks Ltd delivers automotive tyre assemblies to AutoMotive Corp Pune Assembly Plant.",
        "page_count": 1,
        "extraction_status": "done",
    },
    {
        "filename": "PO_GripSeal_AutoMotive.pdf",
        "doc_type": "purchase_order",
        "file_path": "data/sample_docs/PO_GripSeal_AutoMotive.pdf",
        "raw_text": "[DEMONSTRATION SAMPLE] Purchase Order: GripSeal Components delivers rubber sealing gaskets to AutoMotive Corp Pune Assembly Plant.",
        "page_count": 1,
        "extraction_status": "done",
    },
    {
        "filename": "Procurement_Note_07.txt",
        "doc_type": "procurement_note",
        "file_path": "data/sample_docs/Procurement_Note_07.txt",
        "raw_text": "[DEMONSTRATION SAMPLE] Procurement Note: RubberCore sourcing carbon black from PetroChem Asia as primary supplier.",
        "page_count": 1,
        "extraction_status": "done",
    },
]

# 2. Suppliers
# Automotive Manufacturer (Tier 0 reference), Tier 1, Tier 2, Tier 3, and Alternative
SAMPLE_SUPPLIERS = [
    {
        "name": "AutoMotive Corp",
        "entity_type": "manufacturer",
        "country": "India",
        "region": "South Asia",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "capacity_per_month": None,
        "base_risk": 0.0,
        "is_active": True,
    },
    {
        "name": "TyreWorks Ltd",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "capacity_per_month": 5000.0,
        "base_risk": 15.0,
        "is_active": True,
    },
    {
        "name": "GripSeal Components",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 18.9220,
        "longitude": 72.8347,
        "capacity_per_month": 3000.0,
        "base_risk": 10.0,
        "is_active": True,
    },
    {
        "name": "RubberCore Industries",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "capacity_per_month": 200.0,
        "base_risk": 25.0,
        "is_active": True,
    },
    {
        "name": "GreenLatex Pvt Ltd",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 9.9312,
        "longitude": 76.2673,
        "capacity_per_month": 120.0,
        "base_risk": 35.0,
        "is_active": True,
    },
    {
        "name": "PetroChem Asia",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 22.3072,
        "longitude": 73.1812,
        "capacity_per_month": 150.0,
        "base_risk": 20.0,
        "is_active": True,
    },
    {
        "name": "SouthAsia Latex Co",
        "entity_type": "supplier",
        "country": "India",
        "region": "South Asia",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "capacity_per_month": 90.0,
        "base_risk": 20.0,
        "is_active": True,
    },
]

# 3. Aliases
SAMPLE_ALIASES = [
    {"supplier_name": "GreenLatex Pvt Ltd", "alias": "GreenLatex", "match_score": 0.95, "resolved_by": "rule"},
    {"supplier_name": "GreenLatex Pvt Ltd", "alias": "Green Latex Pvt. Ltd.", "match_score": 0.98, "resolved_by": "rule"},
    {"supplier_name": "RubberCore Industries", "alias": "RubberCore", "match_score": 0.98, "resolved_by": "rule"},
]

# 4. Materials
SAMPLE_MATERIALS = [
    {"name": "Natural Latex", "material_type": "raw", "unit": "MT", "category": "rubber"},
    {"name": "Carbon Black", "material_type": "raw", "unit": "MT", "category": "chemicals"},
    {"name": "Processed Rubber", "material_type": "part", "unit": "MT", "category": "rubber"},
    {"name": "Tyres", "material_type": "assembly", "unit": "units", "category": "automotive_components"},
    {"name": "Rubber Seals", "material_type": "part", "unit": "units", "category": "automotive_components"},
]

# 5. Supplier Materials (Capabilities)
SAMPLE_SUPPLIER_MATERIALS = [
    {"supplier_name": "GreenLatex Pvt Ltd", "material_name": "Natural Latex", "capacity_per_month": 120.0, "typical_lead_time_days": 21, "is_qualified": True},
    {"supplier_name": "PetroChem Asia", "material_name": "Carbon Black", "capacity_per_month": 150.0, "typical_lead_time_days": 14, "is_qualified": True},
    {"supplier_name": "SouthAsia Latex Co", "material_name": "Natural Latex", "capacity_per_month": 90.0, "typical_lead_time_days": 14, "is_qualified": True},
    {"supplier_name": "RubberCore Industries", "material_name": "Processed Rubber", "capacity_per_month": 200.0, "typical_lead_time_days": 10, "is_qualified": True},
    {"supplier_name": "TyreWorks Ltd", "material_name": "Tyres", "capacity_per_month": 5000.0, "typical_lead_time_days": 7, "is_qualified": True},
    {"supplier_name": "GripSeal Components", "material_name": "Rubber Seals", "capacity_per_month": 3000.0, "typical_lead_time_days": 5, "is_qualified": True},
]

# 6. Plants
SAMPLE_PLANTS = [
    {"manufacturer_name": "AutoMotive Corp", "name": "Pune Assembly Plant", "location": "Pune, Maharashtra, India"},
]

# 7. Products
SAMPLE_PRODUCTS = [
    {"name": "Sedan X", "unit_revenue": 1200000.0},
]

# 8. Production Lines
SAMPLE_PRODUCTION_LINES = [
    {"plant_name": "Pune Assembly Plant", "product_name": "Sedan X", "name": "Line A", "units_per_day": 50.0, "daily_revenue": 60000000.0},
    {"plant_name": "Pune Assembly Plant", "product_name": "Sedan X", "name": "Line B", "units_per_day": 30.0, "daily_revenue": 36000000.0},
]

# 9. Line Requirements
SAMPLE_LINE_REQUIREMENTS = [
    {"line_name": "Line A", "material_name": "Tyres", "qty_per_day": 200.0, "criticality": "high", "safety_stock_days": 4},
    {"line_name": "Line B", "material_name": "Rubber Seals", "qty_per_day": 120.0, "criticality": "high", "safety_stock_days": 5},
]

# 10. Evidence (supporting documents)
SAMPLE_EVIDENCE = [
    {
        "document_filename": "PO_1042.pdf",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] GreenLatex to supply 40 MT of natural latex to RubberCore monthly.",
        "llm_confidence": 0.92,
        "rel_key": ("GreenLatex Pvt Ltd", "RubberCore Industries", "Natural Latex"),
    },
    {
        "document_filename": "Contract_RubberCore_TyreWorks.txt",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] RubberCore Industries agrees to deliver processed rubber compound to TyreWorks Ltd.",
        "llm_confidence": 0.95,
        "rel_key": ("RubberCore Industries", "TyreWorks Ltd", "Processed Rubber"),
    },
    {
        "document_filename": "Contract_RubberCore_GripSeal.txt",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] RubberCore Industries agrees to supply processed rubber compound to GripSeal Components.",
        "llm_confidence": 0.95,
        "rel_key": ("RubberCore Industries", "GripSeal Components", "Processed Rubber"),
    },
    {
        "document_filename": "PO_TyreWorks_AutoMotive.pdf",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] TyreWorks Ltd to deliver 4000 units of tyres to AutoMotive Corp Pune Assembly Plant.",
        "llm_confidence": 0.98,
        "rel_key": ("TyreWorks Ltd", "AutoMotive Corp", "Tyres"),
    },
    {
        "document_filename": "PO_GripSeal_AutoMotive.pdf",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] GripSeal Components to supply 2500 units of rubber seals to AutoMotive Corp.",
        "llm_confidence": 0.98,
        "rel_key": ("GripSeal Components", "AutoMotive Corp", "Rubber Seals"),
    },
    {
        "document_filename": "Procurement_Note_07.txt",
        "page": 1,
        "chunk_index": 0,
        "snippet": "[DEMONSTRATION EVIDENCE] RubberCore sourcing carbon black from PetroChem Asia as primary supplier.",
        "llm_confidence": 0.88,
        "rel_key": ("PetroChem Asia", "RubberCore Industries", "Carbon Black"),
    },
]

# 11. Relationships
# IMPORTANT: 'tier' is explicitly None (NULL) per DATABASE_SCHEMA.md Section 6.
# Tiers are derived dynamically by the Graph service, NOT hardcoded in seed data.
SAMPLE_RELATIONSHIPS = [
    {
        "supplier_name": "GreenLatex Pvt Ltd",
        "buyer_name": "RubberCore Industries",
        "material_name": "Natural Latex",
        "tier": None,
        "lead_time_days": 21,
        "share_pct": 70.0,
        "inventory_days": 5,
        "quantity_per_month": 40.0,
        "confidence": 0.92,
        "status": "approved",
    },
    {
        "supplier_name": "PetroChem Asia",
        "buyer_name": "RubberCore Industries",
        "material_name": "Carbon Black",
        "tier": None,
        "lead_time_days": 14,
        "share_pct": 80.0,
        "inventory_days": 7,
        "quantity_per_month": 30.0,
        "confidence": 0.88,
        "status": "approved",
    },
    {
        "supplier_name": "RubberCore Industries",
        "buyer_name": "TyreWorks Ltd",
        "material_name": "Processed Rubber",
        "tier": None,
        "lead_time_days": 10,
        "share_pct": 75.0,
        "inventory_days": 4,
        "quantity_per_month": 60.0,
        "confidence": 0.95,
        "status": "approved",
    },
    {
        "supplier_name": "RubberCore Industries",
        "buyer_name": "GripSeal Components",
        "material_name": "Processed Rubber",
        "tier": None,
        "lead_time_days": 10,
        "share_pct": 85.0,
        "inventory_days": 6,
        "quantity_per_month": 40.0,
        "confidence": 0.95,
        "status": "approved",
    },
    {
        "supplier_name": "TyreWorks Ltd",
        "buyer_name": "AutoMotive Corp",
        "material_name": "Tyres",
        "tier": None,
        "lead_time_days": 7,
        "share_pct": 100.0,
        "inventory_days": 3,
        "quantity_per_month": 4000.0,
        "confidence": 0.98,
        "status": "approved",
    },
    {
        "supplier_name": "GripSeal Components",
        "buyer_name": "AutoMotive Corp",
        "material_name": "Rubber Seals",
        "tier": None,
        "lead_time_days": 5,
        "share_pct": 100.0,
        "inventory_days": 4,
        "quantity_per_month": 2500.0,
        "confidence": 0.98,
        "status": "approved",
    },
]

# 12. Disruption Event (Sample baseline event)
# is_simulated is explicitly True (the only documented table containing is_simulated)
SAMPLE_EVENTS = [
    {
        "supplier_name": "GreenLatex Pvt Ltd",
        "event_type": "shutdown",
        "severity": 5,
        "start_date": date(2026, 11, 20),
        "expected_duration_days": 30,
        "description": "[DEMONSTRATION EVENT] Factory closed after regional flooding in plantation district.",
        "source": "simulated",
        "is_simulated": True,
    },
]
