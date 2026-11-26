"""
Unit and integration tests for Document Upload and Management API (Milestone 4: TASK-021).
Conforms to project-docs/API_SPEC.md Section 4.2.
Tests use isolated temporary SQLite databases and direct router-function invocations,
following the repository standard established in tests/test_suppliers.py and tests/test_graph_api.py.
"""

import os
import io
import json
import pytest
from pathlib import Path
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.config import settings
from backend.database import get_db, init_db
from backend.services.document_parser import parse_document, ParsedDocument
from backend.services.document_processor import process_document
from backend.api.documents import (
    upload_documents,
    load_samples,
    list_documents,
    get_document_detail,
    get_document_evidence,
    EXPECTED_SAMPLE_FILES,
)
from backend.models.schemas import (
    LoadSamplesResponse,
    DocumentListResponse,
    DocumentDetailResponse,
    DocumentEvidenceResponse,
    DocumentEvidenceItem,
)
from backend.models.db import (
    Document,
    Supplier,
    Material,
    Evidence,
    Relationship,
    RelationshipEvidence,
)


@pytest.fixture
def doc_api_db(tmp_path, monkeypatch):
    """
    Creates an isolated temporary SQLite database and temporary upload directory.
    Ensures zero interaction with the production tierlens.db.
    """
    test_upload_dir = str(tmp_path / "uploads")
    monkeypatch.setattr(settings, "UPLOAD_DIR", test_upload_dir)

    test_db_path = tmp_path / "test_docs.db"
    engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    init_db(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


# =============================================================================
# Route Registration Tests
# =============================================================================

def test_document_routes_registered():
    """Verifies that all document routes are registered on both root and /api/v1 prefixes."""
    routes = {r.path for r in app.routes}
    assert "/documents/upload" in routes
    assert f"{settings.API_PREFIX}/documents/upload" in routes
    assert "/documents/load-samples" in routes
    assert f"{settings.API_PREFIX}/documents/load-samples" in routes
    assert "/documents" in routes
    assert f"{settings.API_PREFIX}/documents" in routes
    assert "/documents/{id}" in routes
    assert f"{settings.API_PREFIX}/documents/{{id}}" in routes
    assert "/documents/{id}/evidence" in routes
    assert f"{settings.API_PREFIX}/documents/{{id}}/evidence" in routes


# =============================================================================
# Document Upload Tests (POST /documents/upload)
# =============================================================================

def test_upload_single_valid_pdf(doc_api_db):
    """Verifies uploading a single valid PDF file returns 202 Accepted, auto-processes to done, and creates records."""
    with open("data/sample_docs/PO_1042.pdf", "rb") as f:
        pdf_content = f.read()
    upload = UploadFile(filename="PO_1042.pdf", file=io.BytesIO(pdf_content))

    response = upload_documents(files=[upload], doc_type=None, db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 202

    data = json.loads(response.body)
    assert "documents" in data
    assert len(data["documents"]) == 1

    doc_item = data["documents"][0]
    assert doc_item["filename"] == "PO_1042.pdf"
    assert doc_item["extraction_status"] == "pending"
    assert isinstance(doc_item["id"], int)

    # Verify database record updated by automatic processing
    db_doc = doc_api_db.query(Document).filter(Document.id == doc_item["id"]).first()
    assert db_doc is not None
    assert db_doc.filename == "PO_1042.pdf"
    assert db_doc.doc_type == "purchase_order"
    assert db_doc.extraction_status == "done"
    assert db_doc.page_count == 2
    assert "GreenLatex" in db_doc.raw_text
    assert os.path.exists(db_doc.file_path)

    # Verify on-disk file content
    with open(db_doc.file_path, "rb") as f:
        assert f.read() == pdf_content

    # Verify evidence records created
    evidence = doc_api_db.query(Evidence).filter(Evidence.document_id == db_doc.id).all()
    assert len(evidence) >= 2


def test_upload_multiple_valid_files(doc_api_db):
    """Verifies uploading multiple files of different supported formats (.pdf, .txt, .csv) auto-processes all."""
    with open("data/sample_docs/PO_1042.pdf", "rb") as f:
        pdf_content = f.read()
    f1 = UploadFile(filename="Contract_A.txt", file=io.BytesIO(b"Contract between Alpha Corp and Beta Ltd for supply of Raw Material."))
    f2 = UploadFile(filename="Data_B.csv", file=io.BytesIO(b"id,supplier,material\n1,Alpha,Latex\n"))
    f3 = UploadFile(filename="PO_Sample.pdf", file=io.BytesIO(pdf_content))

    response = upload_documents(files=[f1, f2, f3], doc_type=None, db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 202

    data = json.loads(response.body)
    assert len(data["documents"]) == 3

    filenames = [d["filename"] for d in data["documents"]]
    assert "Contract_A.txt" in filenames
    assert "Data_B.csv" in filenames
    assert "PO_Sample.pdf" in filenames

    # Verify all 3 saved in database and all automatically processed to 'done'
    docs = doc_api_db.query(Document).all()
    assert len(docs) == 3
    assert all(d.extraction_status == "done" for d in docs)
    assert all(d.page_count >= 1 for d in docs)
    assert all(d.raw_text is not None and len(d.raw_text) > 0 for d in docs)


def test_upload_invalid_extension_rejected_415(doc_api_db):
    """Verifies that uploading an unsupported file extension returns HTTP 415 UNSUPPORTED_FILE_TYPE."""
    f = UploadFile(filename="malicious_payload.exe", file=io.BytesIO(b"\x4d\x5aBinary content"))

    response = upload_documents(files=[f], doc_type=None, db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 415

    data = json.loads(response.body)
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "malicious_payload.exe" in data["error"]["message"]

    # Verify no file or record saved
    assert doc_api_db.query(Document).count() == 0


def test_upload_oversized_file_rejected_413(doc_api_db, monkeypatch):
    """Verifies that uploading a file exceeding MAX_UPLOAD_SIZE_BYTES returns HTTP 413 FILE_TOO_LARGE."""
    # Monkeypatch limit to 200 bytes for fast test execution
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 200)

    large_content = b"A" * 201
    f = UploadFile(filename="large_po.pdf", file=io.BytesIO(large_content))

    response = upload_documents(files=[f], doc_type=None, db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 413

    data = json.loads(response.body)
    assert "error" in data
    assert data["error"]["code"] == "FILE_TOO_LARGE"

    # Verify no file or record saved
    assert doc_api_db.query(Document).count() == 0


def test_upload_empty_files_rejected_400(doc_api_db):
    """Verifies that uploading an empty list of files returns HTTP 400 BAD_REQUEST."""
    response = upload_documents(files=[], doc_type=None, db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 400

    data = json.loads(response.body)
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"


def test_upload_explicit_and_auto_detected_doc_type(doc_api_db):
    """Verifies explicit doc_type form parameter and auto-detection fallback."""
    # 1. Explicit doc_type
    f1 = UploadFile(filename="CustomFile.txt", file=io.BytesIO(b"Sample content"))
    res1 = upload_documents(files=[f1], doc_type="supplier_record", db=doc_api_db)
    assert isinstance(res1, JSONResponse)
    assert res1.status_code == 202
    doc_id1 = json.loads(res1.body)["documents"][0]["id"]
    doc1 = doc_api_db.query(Document).filter(Document.id == doc_id1).first()
    assert doc1.doc_type == "supplier_record"

    # 2. Auto-detected from filename keywords
    f2 = UploadFile(filename="Procurement_Note_07.txt", file=io.BytesIO(b"Procurement details"))
    res2 = upload_documents(files=[f2], doc_type=None, db=doc_api_db)
    assert isinstance(res2, JSONResponse)
    assert res2.status_code == 202
    doc_id2 = json.loads(res2.body)["documents"][0]["id"]
    doc2 = doc_api_db.query(Document).filter(Document.id == doc_id2).first()
    assert doc2.doc_type == "procurement_note"


def test_upload_invalid_doc_type_rejected_422(doc_api_db):
    """Verifies invalid doc_type returns HTTP 422 VALIDATION_ERROR."""
    f = UploadFile(filename="Valid.pdf", file=io.BytesIO(b"%PDF content"))
    response = upload_documents(files=[f], doc_type="invalid_unknown_type", db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 422

    data = json.loads(response.body)
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert doc_api_db.query(Document).count() == 0


# =============================================================================
# Document Load Samples Tests (POST /documents/load-samples)
# =============================================================================

def test_load_samples_success_and_parse(doc_api_db):
    """Verifies loading bundled synthetic sample documents returns 202, auto-processes all 6, and creates evidence."""
    response = load_samples(db=doc_api_db)
    assert isinstance(response, LoadSamplesResponse)
    assert response.loaded == 6
    assert response.queued_for_extraction == 6

    # Verify 6 database records
    docs = doc_api_db.query(Document).all()
    assert len(docs) == 6

    expected_files = {
        "PO_1042.pdf": "purchase_order",
        "Contract_RubberCore_TyreWorks.txt": "contract",
        "Contract_RubberCore_GripSeal.txt": "contract",
        "PO_TyreWorks_AutoMotive.pdf": "purchase_order",
        "PO_GripSeal_AutoMotive.pdf": "purchase_order",
        "Procurement_Note_07.txt": "procurement_note",
    }

    for doc in docs:
        assert doc.filename in expected_files
        assert doc.doc_type == expected_files[doc.filename]
        assert doc.extraction_status == "done"
        assert os.path.exists(doc.file_path)
        assert doc.raw_text is not None and len(doc.raw_text.strip()) > 0
        assert doc.page_count is not None and doc.page_count >= 1

        # Verify evidence records created
        ev_count = doc_api_db.query(Evidence).filter(Evidence.document_id == doc.id).count()
        assert ev_count >= 1

        # Verify all six copied files are successfully parseable using parse_document
        parsed = parse_document(doc.file_path)
        assert isinstance(parsed, ParsedDocument)
        assert parsed.page_count >= 1
        assert len(parsed.raw_text.strip()) > 0
        assert len(parsed.chunks) >= 1

        if doc.filename == "PO_1042.pdf":
            assert doc.page_count == 2
            assert ev_count >= 2
            assert parsed.page_count == 2
            assert len(parsed.chunks) >= 2


def test_load_samples_idempotency_and_preserves_user_docs(doc_api_db):
    """Verifies calling load-samples repeatedly creates no duplicates and preserves unrelated user documents and evidence."""
    # Seed an unrelated user-uploaded document
    user_doc = Document(
        id=999,
        filename="User_Invoice.pdf",
        doc_type="invoice",
        file_path="/tmp/user_invoice.pdf",
        extraction_status="done",
    )
    doc_api_db.add(user_doc)
    doc_api_db.commit()

    res1 = load_samples(db=doc_api_db)
    assert res1.loaded == 6

    ev_count_1 = doc_api_db.query(Evidence).count()
    assert ev_count_1 >= 6

    res2 = load_samples(db=doc_api_db)
    assert res2.loaded == 6

    ev_count_2 = doc_api_db.query(Evidence).count()
    assert ev_count_1 == ev_count_2  # Reprocessing does not duplicate Evidence records!

    # Total count in database must be 7 (6 samples + 1 user document)
    assert doc_api_db.query(Document).count() == 7

    # Verify user document was not modified or removed
    db_user_doc = doc_api_db.query(Document).filter(Document.id == 999).first()
    assert db_user_doc is not None
    assert db_user_doc.filename == "User_Invoice.pdf"
    assert db_user_doc.extraction_status == "done"


def test_load_samples_one_missing_file_rejected(doc_api_db, monkeypatch, tmp_path):
    """Verifies 404 and no partial DB insertion or file copying when one sample file is missing."""
    temp_samples = tmp_path / "partial_samples_one_missing"
    temp_samples.mkdir(parents=True, exist_ok=True)

    # Copy 5 out of 6 expected files (omit PO_1042.pdf)
    src_dir = Path("data/sample_docs")
    for f in EXPECTED_SAMPLE_FILES:
        if f != "PO_1042.pdf":
            (temp_samples / f).write_bytes((src_dir / f).read_bytes())

    monkeypatch.setattr(settings, "SAMPLE_DOCS_DIR", str(temp_samples))

    doc_count_before = doc_api_db.query(Document).count()
    upload_dir_before = os.listdir(settings.UPLOAD_DIR) if os.path.exists(settings.UPLOAD_DIR) else []

    response = load_samples(db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 404

    data = json.loads(response.body)
    assert data["error"]["code"] == "NOT_FOUND"
    assert "PO_1042.pdf" in data["error"]["message"]
    assert "PO_1042.pdf" in data["error"]["details"]["missing_files"]

    # Verify no partial database insertion
    assert doc_api_db.query(Document).count() == doc_count_before

    # Verify no partial file copying
    upload_dir_after = os.listdir(settings.UPLOAD_DIR) if os.path.exists(settings.UPLOAD_DIR) else []
    assert upload_dir_after == upload_dir_before


def test_load_samples_multiple_missing_files_rejected(doc_api_db, monkeypatch, tmp_path):
    """Verifies 404, lists all missing files, and prevents partial DB insertion or file copying."""
    temp_samples = tmp_path / "partial_samples_multiple_missing"
    temp_samples.mkdir(parents=True, exist_ok=True)

    # Copy only 2 files
    src_dir = Path("data/sample_docs")
    (temp_samples / "PO_1042.pdf").write_bytes((src_dir / "PO_1042.pdf").read_bytes())
    (temp_samples / "Contract_RubberCore_TyreWorks.txt").write_bytes((src_dir / "Contract_RubberCore_TyreWorks.txt").read_bytes())

    monkeypatch.setattr(settings, "SAMPLE_DOCS_DIR", str(temp_samples))

    doc_count_before = doc_api_db.query(Document).count()

    response = load_samples(db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 404

    data = json.loads(response.body)
    assert data["error"]["code"] == "NOT_FOUND"
    missing = data["error"]["details"]["missing_files"]
    assert len(missing) == 4
    assert "Contract_RubberCore_GripSeal.txt" in missing
    assert "PO_TyreWorks_AutoMotive.pdf" in missing
    assert "PO_GripSeal_AutoMotive.pdf" in missing
    assert "Procurement_Note_07.txt" in missing

    # Verify no partial database insertion
    assert doc_api_db.query(Document).count() == doc_count_before


def test_load_samples_missing_dir(doc_api_db, monkeypatch, tmp_path):
    """Verifies 404 NOT_FOUND when sample_docs directory does not exist."""
    non_existent = str(tmp_path / "missing_samples_dir")
    monkeypatch.setattr(settings, "SAMPLE_DOCS_DIR", non_existent)

    response = load_samples(db=doc_api_db)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 404
    data = json.loads(response.body)
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# Document Listing Tests (GET /documents)
# =============================================================================

def test_list_documents_default_and_pagination(doc_api_db):
    """Verifies listing documents with default ordering and pagination."""
    # Seed 4 test documents
    for i in range(1, 5):
        doc = Document(
            id=i,
            filename=f"Doc_{i}.pdf",
            doc_type="purchase_order",
            file_path=f"/tmp/Doc_{i}.pdf",
            extraction_status="done" if i % 2 == 0 else "pending",
        )
        doc_api_db.add(doc)
    doc_api_db.commit()

    # Default listing (first page)
    res = list_documents(extraction_status=None, doc_type=None, limit=2, offset=0, db=doc_api_db)
    assert isinstance(res, DocumentListResponse)
    assert res.total == 4
    assert len(res.items) == 2
    assert res.limit == 2
    assert res.offset == 0

    # Second page
    res_page2 = list_documents(extraction_status=None, doc_type=None, limit=2, offset=2, db=doc_api_db)
    assert isinstance(res_page2, DocumentListResponse)
    assert len(res_page2.items) == 2
    assert res_page2.offset == 2


def test_list_documents_filtering(doc_api_db):
    """Verifies filtering documents by extraction_status and doc_type."""
    d1 = Document(id=1, filename="Doc1.pdf", doc_type="contract", file_path="/tmp/1", extraction_status="done")
    d2 = Document(id=2, filename="Doc2.pdf", doc_type="purchase_order", file_path="/tmp/2", extraction_status="pending")
    d3 = Document(id=3, filename="Doc3.pdf", doc_type="contract", file_path="/tmp/3", extraction_status="pending")
    doc_api_db.add_all([d1, d2, d3])
    doc_api_db.commit()

    # Filter by extraction_status: done
    res_status = list_documents(extraction_status="done", doc_type=None, limit=50, offset=0, db=doc_api_db)
    assert isinstance(res_status, DocumentListResponse)
    assert res_status.total == 1
    assert res_status.items[0].id == 1

    # Filter by doc_type: contract
    res_type = list_documents(extraction_status=None, doc_type="contract", limit=50, offset=0, db=doc_api_db)
    assert isinstance(res_type, DocumentListResponse)
    assert res_type.total == 2


def test_list_documents_relationships_found_count(doc_api_db):
    """Verifies relationships_found correctly counts distinct relationships linked via evidence."""
    # Seed document
    doc = Document(id=10, filename="PO_Linked.pdf", doc_type="purchase_order", file_path="/tmp/p", extraction_status="done")
    # Seed suppliers and material
    s1 = Supplier(id=1, name="AutoCorp", entity_type="manufacturer", country="India", is_active=True)
    s2 = Supplier(id=2, name="PartMaker", entity_type="supplier", country="India", is_active=True)
    m1 = Material(id=1, name="Rubber", material_type="raw")
    m2 = Material(id=2, name="Steel", material_type="raw")
    doc_api_db.add_all([doc, s1, s2, m1, m2])
    doc_api_db.flush()

    # Evidence linked to doc
    ev1 = Evidence(id=1, document_id=10, page=1, snippet="Snippet 1", llm_confidence=0.9)
    ev2 = Evidence(id=2, document_id=10, page=2, snippet="Snippet 2", llm_confidence=0.85)
    doc_api_db.add_all([ev1, ev2])
    doc_api_db.flush()

    # Primary relationship 1 linked to ev1
    rel1 = Relationship(id=1, supplier_id=2, buyer_id=1, material_id=1, status="approved", evidence_id=1)
    # Junction relationship 2 linked to ev2
    rel2 = Relationship(id=2, supplier_id=2, buyer_id=1, material_id=2, status="pending")
    doc_api_db.add_all([rel1, rel2])
    doc_api_db.flush()

    re_link = RelationshipEvidence(relationship_id=2, evidence_id=2)
    doc_api_db.add(re_link)
    doc_api_db.commit()

    res = list_documents(extraction_status=None, doc_type=None, limit=10, offset=0, db=doc_api_db)
    assert isinstance(res, DocumentListResponse)
    item = next(d for d in res.items if d.id == 10)
    assert item.relationships_found == 2


# =============================================================================
# Document Detail Tests (GET /documents/{id})
# =============================================================================

def test_get_document_detail_success(doc_api_db):
    """Verifies retrieving document detail including stats (entities, relationships, low_confidence)."""
    doc = Document(
        id=20,
        filename="Contract_Detail.pdf",
        doc_type="contract",
        file_path="/tmp/c",
        page_count=3,
        extraction_status="done",
    )
    s1 = Supplier(id=10, name="OEM", entity_type="manufacturer", country="India", is_active=True)
    s2 = Supplier(id=11, name="Supplier X", entity_type="supplier", country="India", is_active=True)
    m1 = Material(id=10, name="Steel", material_type="raw")
    doc_api_db.add_all([doc, s1, s2, m1])
    doc_api_db.flush()

    ev = Evidence(id=10, document_id=20, page=1, snippet="Excerpt", llm_confidence=0.65)
    doc_api_db.add(ev)
    doc_api_db.flush()

    # Low confidence relationship (< 0.8)
    rel = Relationship(id=10, supplier_id=11, buyer_id=10, material_id=10, confidence=0.65, status="pending", evidence_id=10)
    doc_api_db.add(rel)
    doc_api_db.commit()

    res = get_document_detail(id=20, db=doc_api_db)
    assert isinstance(res, DocumentDetailResponse)
    assert res.id == 20
    assert res.filename == "Contract_Detail.pdf"
    assert res.doc_type == "contract"
    assert res.page_count == 3
    assert res.extraction_status == "done"
    assert res.stats.relationships == 1
    assert res.stats.low_confidence == 1
    assert res.stats.entities == 3  # supplier 11, buyer 10, material 10


def test_get_document_detail_not_found(doc_api_db):
    """Verifies that requesting a non-existent document ID returns HTTP 404 NOT_FOUND."""
    res = get_document_detail(id=99999, db=doc_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404

    data = json.loads(res.body)
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


# =============================================================================
# Document Processing & Evidence Tests (Milestone 4: TASK-022 / Step 3C)
# =============================================================================

def test_upload_txt_auto_processes_and_generates_evidence(doc_api_db):
    """Verifies uploading a TXT document auto-processes to done, sets raw_text and page_count=1, and creates Evidence."""
    txt_content = (
        b"SUPPLY AGREEMENT\n"
        b"Supplier: Apex Polymers\n"
        b"Buyer: TyreWorks Ltd\n"
        b"Material: Natural Latex\n"
        b"Quantity: 50 MT per month\n"
    )
    upload = UploadFile(filename="Supply_Latex_Apex.txt", file=io.BytesIO(txt_content))

    res = upload_documents(files=[upload], doc_type="contract", db=doc_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 202

    db_doc = doc_api_db.query(Document).filter(Document.filename == "Supply_Latex_Apex.txt").first()
    assert db_doc is not None
    assert db_doc.extraction_status == "done"
    assert db_doc.page_count == 1
    assert "Apex Polymers" in db_doc.raw_text

    evidence = (
        doc_api_db.query(Evidence)
        .filter(Evidence.document_id == db_doc.id)
        .order_by(Evidence.chunk_index.asc())
        .all()
    )
    assert len(evidence) >= 1
    assert evidence[0].page == 1
    assert evidence[0].chunk_index == 0
    assert "Apex Polymers" in evidence[0].snippet
    assert evidence[0].llm_confidence is None


def test_upload_corrupt_file_isolated_failure(doc_api_db):
    """Verifies that a corrupt PDF fails in isolation without failing other files in the upload batch."""
    corrupt_upload = UploadFile(filename="corrupt_invoice.pdf", file=io.BytesIO(b"Not a valid PDF byte string"))
    valid_upload = UploadFile(filename="valid_note.txt", file=io.BytesIO(b"Valid procurement text note for operations."))

    res = upload_documents(files=[corrupt_upload, valid_upload], doc_type=None, db=doc_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 202

    docs = doc_api_db.query(Document).all()
    assert len(docs) == 2

    corrupt_doc = next(d for d in docs if d.filename == "corrupt_invoice.pdf")
    valid_doc = next(d for d in docs if d.filename == "valid_note.txt")

    assert corrupt_doc.extraction_status == "failed"
    assert valid_doc.extraction_status == "done"
    assert valid_doc.page_count == 1
    assert "Valid procurement" in valid_doc.raw_text


def test_get_document_evidence_success_ordered(doc_api_db):
    """Verifies GET /documents/{id}/evidence returns ordered items with snippet and metadata."""
    doc = Document(
        id=50,
        filename="MultiPage_PO.pdf",
        doc_type="purchase_order",
        file_path="/tmp/mp.pdf",
        page_count=2,
        extraction_status="done",
    )
    doc_api_db.add(doc)
    doc_api_db.flush()

    ev2 = Evidence(id=502, document_id=50, page=2, chunk_index=0, snippet="Page 2 chunk 0")
    ev1 = Evidence(id=501, document_id=50, page=1, chunk_index=0, snippet="Page 1 chunk 0")
    doc_api_db.add_all([ev2, ev1])
    doc_api_db.commit()

    res = get_document_evidence(id=50, db=doc_api_db)
    assert isinstance(res, DocumentEvidenceResponse)
    assert res.document_id == 50
    assert len(res.evidence) == 2

    # Preserves ascending order: page 1 before page 2
    assert res.evidence[0].id == 501
    assert res.evidence[0].page == 1
    assert res.evidence[0].snippet == "Page 1 chunk 0"
    assert res.evidence[0].relationship is None

    assert res.evidence[1].id == 502
    assert res.evidence[1].page == 2
    assert res.evidence[1].snippet == "Page 2 chunk 0"
    assert res.evidence[1].relationship is None


def test_get_document_evidence_with_primary_and_junction_relationships(doc_api_db):
    """Verifies GET /documents/{id}/evidence returns relationship details for primary and junction linkages."""
    doc = Document(
        id=60,
        filename="Contract_Linked.txt",
        doc_type="contract",
        file_path="/tmp/c_linked.txt",
        page_count=1,
        extraction_status="done",
    )
    s1 = Supplier(id=61, name="Primary Supplier Ltd", entity_type="supplier", country="India", is_active=True)
    s2 = Supplier(id=62, name="Primary Buyer Corp", entity_type="manufacturer", country="India", is_active=True)
    s3 = Supplier(id=63, name="Junction Supplier Inc", entity_type="supplier", country="India", is_active=True)
    s4 = Supplier(id=64, name="Junction Buyer LLC", entity_type="manufacturer", country="India", is_active=True)
    m1 = Material(id=61, name="Synthetic Rubber", material_type="raw")
    m2 = Material(id=62, name="Steel Wire", material_type="part")
    doc_api_db.add_all([doc, s1, s2, s3, s4, m1, m2])
    doc_api_db.flush()

    ev1 = Evidence(id=601, document_id=60, page=1, chunk_index=0, snippet="Primary evidence snippet")
    ev2 = Evidence(id=602, document_id=60, page=1, chunk_index=1, snippet="Junction evidence snippet")
    ev3 = Evidence(id=603, document_id=60, page=1, chunk_index=2, snippet="Unlinked evidence snippet")
    doc_api_db.add_all([ev1, ev2, ev3])
    doc_api_db.flush()

    # Primary relationship link (Relationship.evidence_id == 601)
    rel_primary = Relationship(
        id=701,
        supplier_id=61,
        buyer_id=62,
        material_id=61,
        evidence_id=601,
        confidence=0.95,
        status="approved",
    )
    # Junction relationship link (RelationshipEvidence)
    rel_junction = Relationship(
        id=702,
        supplier_id=63,
        buyer_id=64,
        material_id=62,
        evidence_id=None,
        confidence=0.90,
        status="approved",
    )
    doc_api_db.add_all([rel_primary, rel_junction])
    doc_api_db.flush()

    rel_ev_link = RelationshipEvidence(relationship_id=702, evidence_id=602)
    doc_api_db.add(rel_ev_link)
    doc_api_db.commit()

    res = get_document_evidence(id=60, db=doc_api_db)
    assert isinstance(res, DocumentEvidenceResponse)
    assert res.document_id == 60
    assert len(res.evidence) == 3

    item1 = next(e for e in res.evidence if e.id == 601)
    assert item1.relationship is not None
    assert item1.relationship.id == 701
    assert item1.relationship.supplier == "Primary Supplier Ltd"
    assert item1.relationship.buyer == "Primary Buyer Corp"
    assert item1.relationship.material == "Synthetic Rubber"

    item2 = next(e for e in res.evidence if e.id == 602)
    assert item2.relationship is not None
    assert item2.relationship.id == 702
    assert item2.relationship.supplier == "Junction Supplier Inc"
    assert item2.relationship.buyer == "Junction Buyer LLC"
    assert item2.relationship.material == "Steel Wire"

    item3 = next(e for e in res.evidence if e.id == 603)
    assert item3.relationship is None


def test_get_document_evidence_not_found_404(doc_api_db):
    """Verifies GET /documents/{id}/evidence returns 404 when document does not exist."""
    res = get_document_evidence(id=99999, db=doc_api_db)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404

    data = json.loads(res.body)
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "Document 99999 does not exist." in data["error"]["message"]


def test_get_document_evidence_empty_list(doc_api_db):
    """Verifies GET /documents/{id}/evidence returns empty list when document exists with no evidence."""
    doc = Document(
        id=70,
        filename="No_Evidence.txt",
        doc_type="procurement_note",
        file_path="/tmp/ne.txt",
        extraction_status="pending",
    )
    doc_api_db.add(doc)
    doc_api_db.commit()

    res = get_document_evidence(id=70, db=doc_api_db)
    assert isinstance(res, DocumentEvidenceResponse)
    assert res.document_id == 70
    assert res.evidence == []


def test_process_document_idempotency_and_relationship_safety(doc_api_db, tmp_path):
    """Verifies that reprocessing a document does not duplicate Evidence and preserves Relationship FK links."""
    file_path = tmp_path / "po_reprocess.txt"
    file_path.write_text("Purchase Order: GreenLatex supplies 40 MT latex to RubberCore monthly.", encoding="utf-8")

    doc = Document(
        filename="po_reprocess.txt",
        doc_type="purchase_order",
        file_path=str(file_path),
        extraction_status="pending",
    )
    doc_api_db.add(doc)
    doc_api_db.commit()

    # First processing pass
    success = process_document(doc.id, doc_api_db)
    assert success is True

    evidence_initial = doc_api_db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    assert len(evidence_initial) == 1
    ev_initial_id = evidence_initial[0].id

    # Seed relationship linked to this evidence
    s1 = Supplier(name="GreenLatex Test", entity_type="supplier", country="India", is_active=True)
    s2 = Supplier(name="RubberCore Test", entity_type="supplier", country="India", is_active=True)
    m1 = Material(name="Latex Test", material_type="raw")
    doc_api_db.add_all([s1, s2, m1])
    doc_api_db.flush()

    rel = Relationship(
        supplier_id=s1.id,
        buyer_id=s2.id,
        material_id=m1.id,
        evidence_id=ev_initial_id,
        confidence=0.92,
        status="approved",
    )
    doc_api_db.add(rel)
    doc_api_db.commit()

    # Second processing pass (reprocessing)
    success_reprocess = process_document(doc.id, doc_api_db)
    assert success_reprocess is True

    evidence_after = doc_api_db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    assert len(evidence_after) == 1
    assert evidence_after[0].id == ev_initial_id  # Evidence ID is strictly preserved!

    # Verify relationship link is still intact
    refreshed_rel = doc_api_db.query(Relationship).filter(Relationship.id == rel.id).first()
    assert refreshed_rel is not None
    assert refreshed_rel.evidence_id == ev_initial_id


def test_process_document_preserves_orphaned_linked_evidence(doc_api_db, tmp_path):
    """Verifies that an Evidence record linked to a Relationship is preserved even if omitted from new chunks."""
    file_path = tmp_path / "contract_shrink.txt"
    file_path.write_text("New single chunk content for the contract.", encoding="utf-8")

    doc = Document(
        filename="contract_shrink.txt",
        doc_type="contract",
        file_path=str(file_path),
        extraction_status="pending",
    )
    doc_api_db.add(doc)
    doc_api_db.commit()

    # Seed an unlinked evidence record with a non-existent page/chunk
    ev_unlinked = Evidence(document_id=doc.id, page=98, chunk_index=98, snippet="Old unlinked chunk")
    # Seed a linked evidence record with a non-existent page/chunk
    ev_linked = Evidence(document_id=doc.id, page=99, chunk_index=99, snippet="Old linked chunk")
    doc_api_db.add_all([ev_unlinked, ev_linked])
    doc_api_db.flush()

    s1 = Supplier(name="Supplier Alpha", entity_type="supplier", country="India", is_active=True)
    s2 = Supplier(name="Buyer Beta", entity_type="supplier", country="India", is_active=True)
    m1 = Material(name="Material Gamma", material_type="raw")
    doc_api_db.add_all([s1, s2, m1])
    doc_api_db.flush()

    rel = Relationship(
        supplier_id=s1.id,
        buyer_id=s2.id,
        material_id=m1.id,
        evidence_id=ev_linked.id,
        status="pending",
    )
    doc_api_db.add(rel)
    doc_api_db.commit()

    # Process the document
    success = process_document(doc.id, doc_api_db)
    assert success is True

    # The unlinked old chunk (page=98) should be removed
    assert doc_api_db.query(Evidence).filter(Evidence.id == ev_unlinked.id).first() is None

    # The linked old chunk (page=99) MUST be preserved
    preserved_ev = doc_api_db.query(Evidence).filter(Evidence.id == ev_linked.id).first()
    assert preserved_ev is not None
    assert preserved_ev.id == ev_linked.id

    # The relationship link is still intact
    refreshed_rel = doc_api_db.query(Relationship).filter(Relationship.id == rel.id).first()
    assert refreshed_rel.evidence_id == ev_linked.id


def test_process_document_nonexistent_returns_false(doc_api_db):
    """Verifies that calling process_document with a non-existent ID returns False gracefully."""
    result = process_document(99999, doc_api_db)
    assert result is False

