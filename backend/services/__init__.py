"""
Service layer initialization for TierLens AI backend.
"""

from backend.services.document_parser import (
    parse_document,
    ParsedDocument,
    ParsedChunk,
    DocumentParseError,
    EmptyDocumentError,
    CorruptDocumentError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)
from backend.services.document_processor import process_document
from backend.services.llm_extractor import extract_relationships, normalize_confidence
from backend.services.entity_resolver import (
    EntityResolver,
    entity_resolver,
    ResolutionResult,
    normalize_company_name,
    normalize_material_name,
    infer_material_type,
    infer_material_category,
)
from backend.services.risk_engine import (
    RiskEngine,
    RiskEvaluationResult,
    AffectedNodeInfo,
    LineImpactInfo,
)
from backend.services.simulation_engine import (
    SimulationEngine,
    SimulationResult,
    SimulationOutcome,
    SimulationImprovement,
    MitigationInput,
    AlternativeRecommendation,
)

__all__ = [
    "parse_document",
    "ParsedDocument",
    "ParsedChunk",
    "DocumentParseError",
    "EmptyDocumentError",
    "CorruptDocumentError",
    "EncryptedDocumentError",
    "UnsupportedFormatError",
    "process_document",
    "extract_relationships",
    "normalize_confidence",
    "EntityResolver",
    "entity_resolver",
    "ResolutionResult",
    "normalize_company_name",
    "normalize_material_name",
    "infer_material_type",
    "infer_material_category",
    "RiskEngine",
    "RiskEvaluationResult",
    "AffectedNodeInfo",
    "LineImpactInfo",
    "SimulationEngine",
    "SimulationResult",
    "SimulationOutcome",
    "SimulationImprovement",
    "MitigationInput",
    "AlternativeRecommendation",
]

