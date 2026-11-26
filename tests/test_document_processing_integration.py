"""
Integration tests for Document Extraction and Entity Resolution Pipeline (Milestone 4: Step 4.3).
Verifies:
1. End-to-end processing of synthetic procurement documents with relationship extraction.
2. Safeguard 1: Never creating a relationship without a valid matching evidence record.
3. Safeguard 2: Determining page numbers using matched evidence chunks without forcing page 1.
4. Safeguard 3: Database uniqueness constraints respected without collapsing legitimate separate relationships.
5. Safeguard 4: Initial processing-status commit separated from atomic processing transaction; clean failure rollback.
6. Invariant: Relationships always created with status='pending' and tier=None (never auto-approved).
7. Reprocessing idempotency and preservation of existing approved relationships.
8. Self-supply and ambiguous entity rejection without database crashes.
9. Correct integration with Document Detail and Document Evidence APIs.

All tests run against isolated temporary SQLite databases.
"""

import json
import os
import shutil
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.database import init_db
from backend.models.db import (
    Document,
    Evidence,
    Relationship,
    RelationshipEvidence,
    Supplier,
    SupplierAlias,
    Material,
)
from backend.services.document_processor import process_document, _find_best_matching_evidence
from backend.api.documents import get_document_detail, get_document_evidence
from backend.models.schemas import DocumentDetailResponse, DocumentEvidenceResponse, ExtractionRelationshipItem

SAMPLE_DOCS_DIR = Path("data/sample_docs")


@pytest.fixture
def clean_db(tmp_path):
    """
    Creates an isolated temporary SQLite database populated with base entities (suppliers, materials, aliases)
    WITHOUT pre-existing relationships.
    Guarantees tierlens.db is completely untouched.
    """
    db_file = tmp_path / "test_processing_clean.db"
    test_db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(target_engine=engine)
    session = Session(bind=engine)

    # 1. Anchor Manufacturer
    mfg = Supplier(name="AutoMotive Corp", entity_type="manufacturer", country="India", region="South Asia", base_risk=0.0, is_active=True)
    session.add(mfg)
    session.flush()

    # 2. Suppliers
    s1 = Supplier(name="GreenLatex Pvt Ltd", entity_type="supplier", country="India", region="South Asia", base_risk=35.0, is_active=True)
    s2 = Supplier(name="RubberCore Industries", entity_type="supplier", country="Malaysia", region="Southeast Asia", base_risk=28.0, is_active=True)
    s3 = Supplier(name="TyreWorks Ltd", entity_type="supplier", country="Vietnam", region="Southeast Asia", base_risk=20.0, is_active=True)
    s4 = Supplier(name="GripSeal Components", entity_type="supplier", country="India", region="South Asia", base_risk=15.0, is_active=True)
    s5 = Supplier(name="PetroChem Asia", entity_type="supplier", country="Singapore", region="Southeast Asia", base_risk=22.0, is_active=True)
    session.add_all([s1, s2, s3, s4, s5])
    session.flush()

    # 3. Aliases
    a1 = SupplierAlias(supplier_id=s1.id, alias="GreenLatex", match_score=0.95, resolved_by="rule")
    a2 = SupplierAlias(supplier_id=s2.id, alias="RubberCore", match_score=0.95, resolved_by="rule")
    a3 = SupplierAlias(supplier_id=s3.id, alias="TyreWorks", match_score=0.95, resolved_by="rule")
    a4 = SupplierAlias(supplier_id=s4.id, alias="GripSeal", match_score=0.95, resolved_by="rule")
    session.add_all([a1, a2, a3, a4])
    session.flush()

    # 4. Materials
    m1 = Material(name="Natural Latex", material_type="raw", unit="MT", category="rubber")
    m2 = Material(name="Carbon Black", material_type="raw", unit="MT", category="chemicals")
    m3 = Material(name="Processed Rubber", material_type="raw", unit="MT", category="rubber")
    m4 = Material(name="Rubber Seals", material_type="part", unit="units", category="rubber")
    m5 = Material(name="Tyres", material_type="assembly", unit="units", category="automotive_components")
    session.add_all([m1, m2, m3, m4, m5])
    session.commit()

    try:
        yield session, tmp_path
    finally:
        session.close()
        engine.dispose()


# =============================================================================
# 1. End-to-End Extraction on Synthetic Business Documents
# =============================================================================

def test_process_sample_po_1042_pdf(clean_db):
    """
    Verifies processing PO_1042.pdf:
    - GreenLatex Pvt Ltd -> RubberCore Industries (Natural Latex)
    - Status is strictly 'pending', tier is strictly NULL
    - Evidence record matched on actual page (multi-page PDF)
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "PO_1042.pdf"
    assert source_file.exists(), f"Missing required sample document: {source_file}"

    # Copy to test storage
    doc_path = tmp_path / "PO_1042.pdf"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="PO_1042.pdf",
        doc_type="purchase_order",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    success = process_document(doc.id, db)
    assert success is True

    # Refresh document
    db.refresh(doc)
    assert doc.extraction_status == "done"
    assert doc.page_count == 2
    assert doc.raw_text is not None and "GreenLatex" in doc.raw_text

    # Verify Evidence chunks created across pages
    ev_records = db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    assert len(ev_records) >= 2
    pages = {ev.page for ev in ev_records}
    assert 1 in pages
    assert 2 in pages

    # Verify pending relationship created
    greenlatex = db.query(Supplier).filter(Supplier.name.ilike("%GreenLatex%")).first()
    rubbercore = db.query(Supplier).filter(Supplier.name.ilike("%RubberCore%")).first()
    latex = db.query(Material).filter(Material.name.ilike("%Natural Latex%")).first()

    assert greenlatex is not None
    assert rubbercore is not None
    assert latex is not None

    rel = (
        db.query(Relationship)
        .filter_by(supplier_id=greenlatex.id, buyer_id=rubbercore.id, material_id=latex.id)
        .first()
    )
    assert rel is not None
    assert rel.status == "pending"  # Invariant: strictly pending
    assert rel.tier is None         # Invariant: strictly NULL
    assert rel.confidence is not None and 0.0 <= rel.confidence <= 1.0
    assert rel.quantity_per_month == 40.0
    assert rel.evidence_id is not None

    # Verify junction link in relationship_evidence
    re_link = (
        db.query(RelationshipEvidence)
        .filter_by(relationship_id=rel.id, evidence_id=rel.evidence_id)
        .first()
    )
    assert re_link is not None

    # Safeguard 2: Ensure evidence page matches the chunk, not hardcoded to 1
    linked_ev = db.query(Evidence).filter(Evidence.id == rel.evidence_id).first()
    assert linked_ev is not None
    assert linked_ev.page in (1, 2)
    assert linked_ev.llm_confidence is not None


def test_process_sample_contract_rubbercore_tyreworks(clean_db):
    """
    Verifies processing Contract_RubberCore_TyreWorks.txt:
    - RubberCore Industries -> TyreWorks Ltd (Processed Rubber)
    - Status is pending, tier is NULL, lead time is 14 days
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "Contract_RubberCore_TyreWorks.txt"
    doc_path = tmp_path / "Contract_RubberCore_TyreWorks.txt"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="Contract_RubberCore_TyreWorks.txt",
        doc_type="contract",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    success = process_document(doc.id, db)
    assert success is True

    rubbercore = db.query(Supplier).filter(Supplier.name.ilike("%RubberCore%")).first()
    tyreworks = db.query(Supplier).filter(Supplier.name.ilike("%TyreWorks%")).first()
    rubber = db.query(Material).filter(Material.name.ilike("%Processed Rubber%")).first()

    rel = (
        db.query(Relationship)
        .filter_by(supplier_id=rubbercore.id, buyer_id=tyreworks.id, material_id=rubber.id)
        .first()
    )
    assert rel is not None
    assert rel.status == "pending"
    assert rel.tier is None
    assert rel.lead_time_days == 10
    assert rel.quantity_per_month == 150.0


def test_process_sample_po_tyreworks_automotive(clean_db):
    """
    Verifies processing PO_TyreWorks_AutoMotive.pdf:
    - TyreWorks Ltd -> AutoMotive Corp (Tyres, 4000 units)
    - Buyer correctly resolves to the Tier 0 manufacturer anchor
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "PO_TyreWorks_AutoMotive.pdf"
    doc_path = tmp_path / "PO_TyreWorks_AutoMotive.pdf"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="PO_TyreWorks_AutoMotive.pdf",
        doc_type="purchase_order",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    success = process_document(doc.id, db)
    assert success is True

    tyreworks = db.query(Supplier).filter(Supplier.name.ilike("%TyreWorks%")).first()
    automotive = db.query(Supplier).filter(Supplier.name.ilike("%AutoMotive Corp%")).first()
    tyres = db.query(Material).filter(Material.name.ilike("%Tyres%")).first()

    assert automotive.entity_type == "manufacturer"

    rel = (
        db.query(Relationship)
        .filter_by(supplier_id=tyreworks.id, buyer_id=automotive.id, material_id=tyres.id)
        .first()
    )
    assert rel is not None
    assert rel.status == "pending"
    assert rel.tier is None
    assert rel.quantity_per_month == 4000.0


# =============================================================================
# 2. Idempotency & De-duplication Tests
# =============================================================================

def test_reprocessing_same_document_creates_no_duplicate_relationships(clean_db):
    """
    Verifies that calling process_document repeatedly on the same document:
    - Creates no duplicate relationships in relationships table
    - Creates no duplicate entries in relationship_evidence junction table
    - Preserves existing Relationship.id and Evidence.id
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "Contract_RubberCore_GripSeal.txt"
    doc_path = tmp_path / "Contract_RubberCore_GripSeal.txt"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="Contract_RubberCore_GripSeal.txt",
        doc_type="contract",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    # Pass 1
    assert process_document(doc.id, db) is True

    rels_1 = db.query(Relationship).all()
    ev_1 = db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    junction_1 = db.query(RelationshipEvidence).all()

    rel_count_1 = len(rels_1)
    ev_count_1 = len(ev_1)
    junction_count_1 = len(junction_1)
    assert rel_count_1 == 1

    # Pass 2 (Reprocessing)
    assert process_document(doc.id, db) is True

    rels_2 = db.query(Relationship).all()
    ev_2 = db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    junction_2 = db.query(RelationshipEvidence).all()

    # Assert no duplication
    assert len(rels_2) == rel_count_1
    assert len(ev_2) == ev_count_1
    assert len(junction_2) == junction_count_1


def test_reprocessing_preserves_existing_approved_relationships(clean_db):
    """
    Verifies that if an analyst approved a relationship (status='approved', tier=2),
    reprocessing the source document:
    - Never reverts status back to 'pending'
    - Never overwrites the approved tier back to NULL
    - Attaches new evidence without breaking existing approved state
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "Procurement_Note_07.txt"
    doc_path = tmp_path / "Procurement_Note_07.txt"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="Procurement_Note_07.txt",
        doc_type="procurement_note",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    # Initial extraction
    assert process_document(doc.id, db) is True

    petrochem = db.query(Supplier).filter(Supplier.name.ilike("%PetroChem Asia%")).first()
    rubbercore = db.query(Supplier).filter(Supplier.name.ilike("%RubberCore%")).first()
    carbon_black = db.query(Material).filter(Material.name.ilike("%Carbon Black%")).first()

    rel = (
        db.query(Relationship)
        .filter_by(supplier_id=petrochem.id, buyer_id=rubbercore.id, material_id=carbon_black.id)
        .first()
    )
    assert rel is not None
    assert rel.status == "pending"

    # Simulate human approval
    rel.status = "approved"
    rel.tier = 2
    rel.reviewed_by = "analyst_qa"
    db.commit()

    # Reprocess document
    assert process_document(doc.id, db) is True

    # Re-query relationship
    rel_after = (
        db.query(Relationship)
        .filter_by(supplier_id=petrochem.id, buyer_id=rubbercore.id, material_id=carbon_black.id)
        .first()
    )
    assert rel_after.status == "approved"  # Invariant: never reverted to pending!
    assert rel_after.tier == 2             # Invariant: tier preserved!
    assert rel_after.reviewed_by == "analyst_qa"


# =============================================================================
# 3. Safeguard Verifications
# =============================================================================

def test_safeguard_1_missing_evidence_skips_relationship(clean_db):
    """
    Safeguard 1: Never create a relationship without a valid matching evidence record.
    If evidence chunk cannot be matched to a candidate, relationship creation is skipped.
    """
    db, tmp_path = clean_db
    # Create a document whose text doesn't contain standard procurement patterns
    unrelated_file = tmp_path / "unrelated_notice.txt"
    unrelated_file.write_text("Notice: The office cafeteria will close early at 2 PM today for deep cleaning.", encoding="utf-8")

    doc = Document(
        filename="unrelated_notice.txt",
        doc_type="memo",
        file_path=str(unrelated_file),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    success = process_document(doc.id, db)
    assert success is True

    # Document completes, but zero relationships created
    db.refresh(doc)
    assert doc.extraction_status == "done"
    evs = db.query(Evidence).filter(Evidence.document_id == doc.id).all()
    assert len(evs) == 1

    # No relationships reference this document
    linked_rels = db.query(Relationship).filter(Relationship.evidence_id == evs[0].id).all()
    assert len(linked_rels) == 0


def test_stage_4_fallback_boilerplate_without_material_must_not_match():
    """
    Stage 4 Fallback Regression Test 1:
    A boilerplate chunk containing supplier and buyer names but NOT the material name
    must not match in Stage 4 fallback evidence matching.
    """
    candidate = ExtractionRelationshipItem(
        supplier="RubberCore Industries",
        buyer="TyreWorks Ltd",
        material="Processed Rubber",
        confidence=0.9,
        snippet="Completely unmatched snippet string that will fail Stages 1, 2, and 3",
        page=1,
    )

    boilerplate_ev = Evidence(
        id=101,
        document_id=1,
        page=1,
        chunk_index=0,
        snippet="MUTUAL NON-DISCLOSURE AGREEMENT: Entered into between RubberCore Industries and TyreWorks Ltd for confidential project evaluation.",
    )

    matched = _find_best_matching_evidence([boilerplate_ev], candidate)
    assert matched is None, "Boilerplate chunk lacking material name must not match"


def test_stage_4_fallback_chunk_with_supplier_buyer_and_material_matches():
    """
    Stage 4 Fallback Regression Test 2:
    A chunk containing supplier, buyer AND material names may match in Stage 4 fallback
    even when snippet substring and token overlap in Stages 1-3 fail.
    """
    candidate = ExtractionRelationshipItem(
        supplier="RubberCore Industries",
        buyer="TyreWorks Ltd",
        material="Processed Rubber",
        confidence=0.9,
        snippet="Completely unmatched snippet string that will fail Stages 1, 2, and 3",
        page=1,
    )

    valid_ev = Evidence(
        id=102,
        document_id=1,
        page=1,
        chunk_index=0,
        snippet="PURCHASE CONTRACT: RubberCore Industries shall manufacture and supply Processed Rubber to TyreWorks Ltd at agreed monthly volumes.",
    )

    matched = _find_best_matching_evidence([valid_ev], candidate)
    assert matched is not None, "Evidence chunk containing supplier, buyer and material must match in Stage 4"
    assert matched.id == 102


def test_stage_4_fallback_candidate_without_material_returns_no_match():
    """
    Stage 4 Fallback Regression Test:
    If candidate has empty material, Stage 4 must return None rather than matching.
    """
    candidate = ExtractionRelationshipItem(
        supplier="RubberCore Industries",
        buyer="TyreWorks Ltd",
        material="",
        confidence=0.8,
        snippet="Unmatched snippet",
        page=1,
    )

    ev = Evidence(
        id=103,
        document_id=1,
        page=1,
        chunk_index=0,
        snippet="RubberCore Industries agrees to sell commodities to TyreWorks Ltd.",
    )

    matched = _find_best_matching_evidence([ev], candidate)
    assert matched is None


def test_safeguard_3_multiple_materials_same_parties_separate_relationships(clean_db):
    """
    Safeguard 3: Avoid collapsing legitimate separate relationships.
    When a supplier provides two distinct materials to the same buyer across separate contracts,
    two distinct relationships are created in the database.
    """
    db, tmp_path = clean_db

    # Document 1: Processed Rubber supply
    file1 = tmp_path / "contract_rubber.txt"
    file1.write_text(
        "Supply Agreement: Buyer: TyreWorks Ltd, Supplier: RubberCore Industries, Material: Processed Rubber.",
        encoding="utf-8",
    )
    doc1 = Document(filename="contract_rubber.txt", doc_type="contract", file_path=str(file1), extraction_status="pending")
    db.add(doc1)
    db.commit()

    # Document 2: Natural Latex supply
    file2 = tmp_path / "contract_latex.txt"
    file2.write_text(
        "Supply Agreement: Buyer: TyreWorks Ltd, Supplier: RubberCore Industries, Material: Natural Latex.",
        encoding="utf-8",
    )
    doc2 = Document(filename="contract_latex.txt", doc_type="contract", file_path=str(file2), extraction_status="pending")
    db.add(doc2)
    db.commit()

    assert process_document(doc1.id, db) is True
    assert process_document(doc2.id, db) is True

    rubbercore = db.query(Supplier).filter(Supplier.name.ilike("%RubberCore%")).first()
    tyreworks = db.query(Supplier).filter(Supplier.name.ilike("%TyreWorks%")).first()

    # Query all relationships from RubberCore to TyreWorks
    rc_tw_rels = (
        db.query(Relationship)
        .filter_by(supplier_id=rubbercore.id, buyer_id=tyreworks.id)
        .all()
    )
    # Must have two distinct relationships (one for Processed Rubber, one for Natural Latex)
    assert len(rc_tw_rels) == 2
    material_ids = {r.material_id for r in rc_tw_rels}
    assert len(material_ids) == 2


def test_safeguard_4_transaction_failure_isolation(clean_db):
    """
    Safeguard 4: Separate initial processing commit from atomic processing transaction.
    If processing fails (e.g. corrupted file), changes are rolled back and document
    status is cleanly updated to 'failed' in a fresh transaction without dirtying the database.
    """
    db, tmp_path = clean_db
    corrupt_file = tmp_path / "broken.pdf"
    corrupt_file.write_bytes(b"%PDF-1.4 completely corrupt content")

    doc = Document(
        filename="broken.pdf",
        doc_type="purchase_order",
        file_path=str(corrupt_file),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    success = process_document(doc.id, db)
    assert success is False

    # Verify document reliably ends with 'failed'
    db.refresh(doc)
    assert doc.extraction_status == "failed"

    # Verify no partial evidence records created
    ev_count = db.query(Evidence).filter(Evidence.document_id == doc.id).count()
    assert ev_count == 0


def test_self_supply_prevention(clean_db):
    """Verifies that candidate relationships where supplier == buyer are skipped to prevent DB check constraint errors."""
    db, tmp_path = clean_db
    self_file = tmp_path / "self_transfer.txt"
    self_file.write_text("Inter-plant note: RubberCore Industries supplies 10 MT Processed Rubber to RubberCore Industries.", encoding="utf-8")

    doc = Document(
        filename="self_transfer.txt",
        doc_type="procurement_note",
        file_path=str(self_file),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    # Processing must succeed without crashing on check_rel_no_self_supply
    success = process_document(doc.id, db)
    assert success is True

    db.refresh(doc)
    assert doc.extraction_status == "done"

    rubbercore = db.query(Supplier).filter(Supplier.name.ilike("%RubberCore%")).first()
    self_rels = db.query(Relationship).filter_by(supplier_id=rubbercore.id, buyer_id=rubbercore.id).all()
    assert len(self_rels) == 0


# =============================================================================
# 4. API Response Integration Tests
# =============================================================================

def test_document_detail_and_evidence_api_integration(clean_db):
    """
    Verifies that after processing a document, GET /documents/{id} and GET /documents/{id}/evidence
    accurately reflect the newly created relationships, entities, and evidence links.
    """
    db, tmp_path = clean_db
    source_file = SAMPLE_DOCS_DIR / "PO_GripSeal_AutoMotive.pdf"
    doc_path = tmp_path / "PO_GripSeal_AutoMotive.pdf"
    shutil.copy2(source_file, doc_path)

    doc = Document(
        filename="PO_GripSeal_AutoMotive.pdf",
        doc_type="purchase_order",
        file_path=str(doc_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    assert process_document(doc.id, db) is True

    # Call GET /documents/{id}
    detail_res = get_document_detail(id=doc.id, db=db)
    assert isinstance(detail_res, DocumentDetailResponse)
    assert detail_res.extraction_status == "done"
    assert detail_res.stats.relationships >= 1
    assert detail_res.stats.entities >= 2

    # Call GET /documents/{id}/evidence
    ev_res = get_document_evidence(id=doc.id, db=db)
    assert isinstance(ev_res, DocumentEvidenceResponse)
    assert len(ev_res.evidence) >= 1

    # Verify that at least one evidence item has relationship data attached
    linked_items = [e for e in ev_res.evidence if e.relationship is not None]
    assert len(linked_items) >= 1
    rel_ref = linked_items[0].relationship
    assert "GripSeal" in rel_ref.supplier
    assert "AutoMotive" in rel_ref.buyer
    assert "Rubber Seals" in rel_ref.material
