"""
Document Ingestion and Management API (Milestone 4: TASK-021).
Conforms to project-docs/API_SPEC.md Section 4.2 and project-docs/ARCHITECTURE.md Section 3.1.
"""

import os
import uuid
import shutil
from typing import Optional, List, Set, Dict, Union
from pathlib import Path
from fastapi import APIRouter, Depends, Query, Path as PathParam, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from backend.config import settings
from backend.database import get_db
from backend.services.document_processor import process_document
from backend.models.db import (
    Document,
    Evidence,
    Relationship,
    RelationshipEvidence,
)
from backend.models.schemas import (
    DocumentUploadItem,
    DocumentUploadResponse,
    LoadSamplesResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentStats,
    DocumentDetailResponse,
    DocumentEvidenceRelationshipRef,
    DocumentEvidenceItem,
    DocumentEvidenceResponse,
)

router = APIRouter(tags=["Documents"])

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".txt", ".csv"}
VALID_DOC_TYPES: Set[str] = {
    "purchase_order",
    "supplier_record",
    "contract",
    "invoice",
    "procurement_note",
}
EXPECTED_SAMPLE_FILES: List[str] = [
    "PO_1042.pdf",
    "Contract_RubberCore_TyreWorks.txt",
    "Contract_RubberCore_GripSeal.txt",
    "PO_TyreWorks_AutoMotive.pdf",
    "PO_GripSeal_AutoMotive.pdf",
    "Procurement_Note_07.txt",
]


def auto_detect_doc_type(filename: str) -> str:
    """
    Auto-detects document type based on filename keywords.
    Defaults to 'purchase_order' if no keyword matches.
    """
    fn = filename.lower()
    if "contract" in fn or "agreement" in fn:
        return "contract"
    if "invoice" in fn or "bill" in fn:
        return "invoice"
    if "procurement" in fn or "note" in fn:
        return "procurement_note"
    if "supplier" in fn or "record" in fn or "vendor" in fn:
        return "supplier_record"
    return "purchase_order"


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=202)
def upload_documents(
    files: List[UploadFile] = File(..., description="One or more PDF, TXT or CSV files (max 10 MB each)"),
    doc_type: Optional[str] = Form(default=None, description="Document type; defaults to auto-detect"),
    db: Session = Depends(get_db),
) -> Union[DocumentUploadResponse, JSONResponse]:
    """
    Upload one or more procurement files. Validates file types and sizes, saves
    sanitized files to disk, and records document metadata in SQLite with initial
    extraction status 'pending'.
    Conforms to API_SPEC.md Section 4.2.
    """
    # 1. Validate doc_type if provided
    resolved_explicit_doc_type: Optional[str] = None
    if doc_type is not None and doc_type.strip():
        norm_type = doc_type.strip().lower()
        if norm_type not in VALID_DOC_TYPES:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid doc_type '{doc_type}'. Allowed types: {', '.join(sorted(VALID_DOC_TYPES))}.",
                        "details": {"doc_type": doc_type, "allowed": sorted(VALID_DOC_TYPES)},
                    }
                },
            )
        resolved_explicit_doc_type = norm_type

    # 2. Validate files list non-empty
    if not files:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "No files provided for upload.",
                    "details": {},
                }
            },
        )

    # 3. Read and pre-validate all files atomically (types and size limits)
    validated_payloads = []
    for file in files:
        original_name = Path(file.filename or "unknown").name
        ext = Path(original_name).suffix.lower()

        # Reject unsupported file type with HTTP 415
        if ext not in ALLOWED_EXTENSIONS:
            return JSONResponse(
                status_code=415,
                content={
                    "error": {
                        "code": "UNSUPPORTED_FILE_TYPE",
                        "message": f"File '{original_name}' has an unsupported file type '{ext}'. Only PDF, TXT and CSV are supported.",
                        "details": {"filename": original_name, "extension": ext, "allowed": sorted(ALLOWED_EXTENSIONS)},
                    }
                },
            )

        # Read content and enforce size limit
        file.file.seek(0)
        content = file.file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"File '{original_name}' exceeds maximum allowed size of 10 MB.",
                        "details": {
                            "filename": original_name,
                            "size_bytes": len(content),
                            "max_bytes": settings.MAX_UPLOAD_SIZE_BYTES,
                        },
                    }
                },
            )

        validated_payloads.append((original_name, ext, content))

    # 4. Save files to disk and record metadata in SQLite
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    uploaded_items: List[DocumentUploadItem] = []

    for original_name, ext, content in validated_payloads:
        # Sanitize and assign unique filename to avoid collision / overwriting
        stored_filename = f"{uuid.uuid4().hex}_{original_name}"
        stored_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

        with open(stored_path, "wb") as f:
            f.write(content)

        file_doc_type = (
            resolved_explicit_doc_type
            if resolved_explicit_doc_type is not None
            else auto_detect_doc_type(original_name)
        )

        doc = Document(
            filename=original_name,
            doc_type=file_doc_type,
            file_path=stored_path,
            raw_text=None,
            page_count=None,
            extraction_status="pending",
        )
        db.add(doc)
        db.flush()

        uploaded_items.append(
            DocumentUploadItem(
                id=doc.id,
                filename=doc.filename,
                extraction_status=doc.extraction_status,
            )
        )

    db.commit()

    # Automatically process uploaded documents synchronously in isolation
    for item in uploaded_items:
        try:
            process_document(item.id, db)
        except Exception:
            pass

    return JSONResponse(
        status_code=202,
        content={"documents": [item.model_dump() for item in uploaded_items]},
    )


@router.post("/documents/load-samples", response_model=LoadSamplesResponse, status_code=202)
def load_samples(
    db: Session = Depends(get_db),
) -> Union[LoadSamplesResponse, JSONResponse]:
    """
    Loads the bundled synthetic dataset from data/sample_docs/ and queues extraction.
    Conforms to API_SPEC.md Section 4.2.
    Validates that all six expected sample files exist prior to file copying or database changes.
    """
    sample_dir = Path(settings.SAMPLE_DOCS_DIR)
    if not sample_dir.exists() or not sample_dir.is_dir():
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Sample documents directory '{settings.SAMPLE_DOCS_DIR}' does not exist.",
                    "details": {},
                }
            },
        )

    # Validate that all expected sample files exist before mutating files or database
    missing_files = [f for f in EXPECTED_SAMPLE_FILES if not (sample_dir / f).is_file()]
    if missing_files:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Missing required sample file(s): {', '.join(sorted(missing_files))}.",
                    "details": {
                        "missing_files": sorted(missing_files),
                        "expected_files": EXPECTED_SAMPLE_FILES,
                    },
                }
            },
        )

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    loaded_count = 0

    for filename in EXPECTED_SAMPLE_FILES:
        sample_file = sample_dir / filename
        file_doc_type = auto_detect_doc_type(filename)

        # Copy sample file to UPLOAD_DIR
        dest_filename = f"sample_{filename}"
        dest_path = os.path.join(settings.UPLOAD_DIR, dest_filename)
        shutil.copy2(sample_file, dest_path)

        # Maintain idempotency: check if document already exists by filename
        existing = db.query(Document).filter(Document.filename == filename).first()
        if existing:
            existing.file_path = dest_path
            existing.doc_type = file_doc_type
            existing.extraction_status = "pending"
        else:
            doc = Document(
                filename=filename,
                doc_type=file_doc_type,
                file_path=dest_path,
                raw_text=None,
                page_count=None,
                extraction_status="pending",
            )
            db.add(doc)

        loaded_count += 1

    db.commit()

    # Automatically process all loaded sample documents synchronously in isolation
    sample_docs = (
        db.query(Document)
        .filter(Document.filename.in_(EXPECTED_SAMPLE_FILES))
        .all()
    )
    for sdoc in sample_docs:
        try:
            process_document(sdoc.id, db)
        except Exception:
            pass

    return LoadSamplesResponse(
        loaded=loaded_count,
        queued_for_extraction=loaded_count,
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    extraction_status: Optional[str] = Query(default=None, description="Filter by extraction status"),
    doc_type: Optional[str] = Query(default=None, description="Filter by document type"),
    limit: int = Query(default=50, ge=1, le=200, description="Page limit (1-200)"),
    offset: int = Query(default=0, ge=0, description="Page offset (>= 0)"),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    List uploaded documents with optional filtering and pagination.
    Computes relationships_found per document.
    Conforms to API_SPEC.md Section 4.2.
    """
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0
    actual_status = extraction_status.strip().lower() if isinstance(extraction_status, str) and extraction_status.strip() else None
    actual_doc_type = doc_type.strip().lower() if isinstance(doc_type, str) and doc_type.strip() else None

    query = db.query(Document)

    if actual_status is not None:
        query = query.filter(Document.extraction_status == actual_status)
    if actual_doc_type is not None:
        query = query.filter(Document.doc_type == actual_doc_type)

    total = query.count()

    docs = (
        query.order_by(Document.id.desc())
        .offset(actual_offset)
        .limit(actual_limit)
        .all()
    )

    doc_ids = [d.id for d in docs]
    doc_rel_map: Dict[int, Set[int]] = {did: set() for did in doc_ids}

    if doc_ids:
        # 1. Primary relationships linked directly via evidence
        primary_links = (
            db.query(Evidence.document_id, Relationship.id)
            .join(Relationship, Relationship.evidence_id == Evidence.id)
            .filter(Evidence.document_id.in_(doc_ids))
            .all()
        )
        for did, rid in primary_links:
            doc_rel_map[did].add(rid)

        # 2. Multi-evidence junction links
        junction_links = (
            db.query(Evidence.document_id, RelationshipEvidence.relationship_id)
            .join(RelationshipEvidence, RelationshipEvidence.evidence_id == Evidence.id)
            .filter(Evidence.document_id.in_(doc_ids))
            .all()
        )
        for did, rid in junction_links:
            doc_rel_map[did].add(rid)

    items = [
        DocumentListItem(
            id=d.id,
            filename=d.filename,
            doc_type=d.doc_type,
            extraction_status=d.extraction_status,
            uploaded_at=d.uploaded_at,
            relationships_found=len(doc_rel_map.get(d.id, set())),
        )
        for d in docs
    ]

    return DocumentListResponse(
        items=items,
        total=total,
        limit=actual_limit,
        offset=actual_offset,
    )


@router.get("/documents/{id}", response_model=DocumentDetailResponse)
def get_document_detail(
    id: int = PathParam(..., ge=1, description="Document ID (>= 1)"),
    db: Session = Depends(get_db),
) -> Union[DocumentDetailResponse, JSONResponse]:
    """
    Retrieves document details and summary statistics:
    - entities count
    - relationships count
    - low_confidence relationships count
    Conforms to API_SPEC.md Section 4.2.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Document {id} does not exist.",
                    "details": {},
                }
            },
        )

    # Gather distinct relationship IDs linked to this document
    linked_rel_ids: Set[int] = set()

    # Primary evidence links
    primary_rels = (
        db.query(Relationship.id)
        .join(Evidence, Relationship.evidence_id == Evidence.id)
        .filter(Evidence.document_id == doc.id)
        .all()
    )
    for r in primary_rels:
        linked_rel_ids.add(r[0])

    # Junction table links
    junction_rels = (
        db.query(RelationshipEvidence.relationship_id)
        .join(Evidence, RelationshipEvidence.evidence_id == Evidence.id)
        .filter(Evidence.document_id == doc.id)
        .all()
    )
    for r in junction_rels:
        linked_rel_ids.add(r[0])

    entities_count = 0
    rel_count = len(linked_rel_ids)
    low_confidence_count = 0

    if linked_rel_ids:
        rels = db.query(Relationship).filter(Relationship.id.in_(linked_rel_ids)).all()
        # Count low confidence (< 0.8)
        low_confidence_count = sum(1 for r in rels if r.confidence is not None and r.confidence < 0.8)

        # Count distinct entities: suppliers (suppliers + buyers) and materials
        entity_tokens: Set[str] = set()
        for r in rels:
            entity_tokens.add(f"supp:{r.supplier_id}")
            entity_tokens.add(f"buyer:{r.buyer_id}")
            entity_tokens.add(f"mat:{r.material_id}")
        entities_count = len(entity_tokens)

    stats = DocumentStats(
        entities=entities_count,
        relationships=rel_count,
        low_confidence=low_confidence_count,
    )

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        doc_type=doc.doc_type,
        page_count=doc.page_count,
        extraction_status=doc.extraction_status,
        uploaded_at=doc.uploaded_at,
        stats=stats,
    )


@router.get("/documents/{id}/evidence", response_model=DocumentEvidenceResponse)
def get_document_evidence(
    id: int = PathParam(..., ge=1, description="Document ID (>= 1)"),
    db: Session = Depends(get_db),
) -> Union[DocumentEvidenceResponse, JSONResponse]:
    """
    Retrieves evidence snippets extracted from a document.
    Conforms to API_SPEC.md Section 4.2.
    Returns HTTP 404 if document does not exist.
    Returns HTTP 200 with empty evidence list if document exists but has no evidence.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Document {id} does not exist.",
                    "details": {},
                }
            },
        )

    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.document_id == id)
        .order_by(
            Evidence.page.asc(),
            Evidence.chunk_index.asc(),
            Evidence.id.asc(),
        )
        .all()
    )

    if not evidence_rows:
        return DocumentEvidenceResponse(
            document_id=id,
            evidence=[],
        )

    ev_ids = [ev.id for ev in evidence_rows]

    # Pre-fetch linked relationships
    primary_rels = (
        db.query(Relationship)
        .options(
            joinedload(Relationship.supplier),
            joinedload(Relationship.buyer),
            joinedload(Relationship.material),
        )
        .filter(Relationship.evidence_id.in_(ev_ids))
        .all()
    )
    rel_by_primary: Dict[int, Relationship] = {r.evidence_id: r for r in primary_rels}

    junction_links = (
        db.query(RelationshipEvidence)
        .options(
            joinedload(RelationshipEvidence.relationship).joinedload(Relationship.supplier),
            joinedload(RelationshipEvidence.relationship).joinedload(Relationship.buyer),
            joinedload(RelationshipEvidence.relationship).joinedload(Relationship.material),
        )
        .filter(RelationshipEvidence.evidence_id.in_(ev_ids))
        .all()
    )
    rel_by_junction: Dict[int, Relationship] = {
        j.evidence_id: j.relationship for j in junction_links if j.relationship is not None
    }

    items: List[DocumentEvidenceItem] = []
    for ev in evidence_rows:
        rel = rel_by_primary.get(ev.id) or rel_by_junction.get(ev.id)
        rel_ref: Optional[DocumentEvidenceRelationshipRef] = None
        if rel is not None:
            rel_ref = DocumentEvidenceRelationshipRef(
                id=rel.id,
                supplier=rel.supplier.name if rel.supplier else "Unknown",
                buyer=rel.buyer.name if rel.buyer else "Unknown",
                material=rel.material.name if rel.material else "Unknown",
            )

        items.append(
            DocumentEvidenceItem(
                id=ev.id,
                page=ev.page,
                snippet=ev.snippet,
                llm_confidence=ev.llm_confidence,
                relationship=rel_ref,
            )
        )

    return DocumentEvidenceResponse(
        document_id=id,
        evidence=items,
    )

