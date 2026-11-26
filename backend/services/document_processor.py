"""
Document processing and evidence generation service for TierLens AI (Milestone 4: TASK-022 & TASK-023).
Processes uploaded and sample procurement documents:
1. Parses stored files into raw text, page counts, and structured chunks.
2. Updates document metadata and extraction status (pending -> processing -> done / failed).
3. Idempotently creates and synchronizes Evidence records while strictly preserving
   foreign key linkages to existing Relationship entities.
4. Extracts structured supplier relationship candidates using AI / pattern extractor.
5. Resolves supplier and material entities via EntityResolver.
6. Idempotently creates and links pending relationships to supporting evidence records.
7. Preserves transaction safety, failure isolation, and never auto-approves relationships.

Conforms to ARCHITECTURE.md Section 3.1, 3.2, 3.3 and DATABASE_SCHEMA.md Section 3.6, 3.7, 3.8.
"""

import re
import logging
from typing import Optional, Set, Dict, Tuple, List
from sqlalchemy.orm import Session

from backend.models.db import (
    Document,
    Evidence,
    Relationship,
    RelationshipEvidence,
)
from backend.services.document_parser import (
    parse_document,
    DocumentParseError,
    ParsedDocument,
)
from backend.services.llm_extractor import extract_relationships
from backend.models.schemas import ExtractionRelationshipItem
from backend.services.entity_resolver import entity_resolver

logger = logging.getLogger(__name__)


def _find_best_matching_evidence(
    doc_evidence: List[Evidence],
    candidate: ExtractionRelationshipItem,
) -> Optional[Evidence]:
    """
    Finds the exact or best-matching Evidence chunk in the document for an extracted candidate relationship.
    Returns None if no reasonable evidence match is found.

    Safeguards:
    1. Never returns an evidence record unless a genuine match/overlap exists.
    2. Determines true page numbers using the matched evidence chunk.
    """
    if not doc_evidence:
        return None

    snippet = (candidate.snippet or "").strip()

    # 1. Exact substring match on candidate's suggested page (if present)
    if candidate.page is not None and snippet:
        for ev in doc_evidence:
            if ev.page == candidate.page:
                if snippet in ev.snippet or ev.snippet.strip() in snippet:
                    return ev

    # 2. Exact substring match across any page in the document
    if snippet:
        for ev in doc_evidence:
            if snippet in ev.snippet or ev.snippet.strip() in snippet:
                return ev

    # 3. High token overlap of snippet in chunk
    if snippet:
        snippet_tokens = set(re.findall(r"\b\w{3,}\b", snippet.lower()))
        best_ev = None
        best_overlap = 0
        for ev in doc_evidence:
            ev_tokens = set(re.findall(r"\b\w{3,}\b", ev.snippet.lower()))
            overlap = len(snippet_tokens & ev_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_ev = ev

        # Require at least 50% of candidate snippet tokens to match
        if best_ev is not None and len(snippet_tokens) > 0 and (best_overlap / len(snippet_tokens)) >= 0.5:
            return best_ev

    # 4. Fallback: Search for co-occurrence of supplier, buyer, and material names in chunk text
    # Safeguard: All three entities must be present in the chunk before returning a match.
    # If the material name is missing, return None so the candidate is skipped safely.
    supp_lower = (candidate.supplier or "").strip().lower()
    buyer_lower = (candidate.buyer or "").strip().lower()
    mat_lower = (candidate.material or "").strip().lower()

    if supp_lower and buyer_lower and mat_lower:
        # Check on candidate page first
        if candidate.page is not None:
            for ev in doc_evidence:
                if ev.page == candidate.page:
                    ev_lower = ev.snippet.lower()
                    if supp_lower in ev_lower and buyer_lower in ev_lower and mat_lower in ev_lower:
                        return ev

        # Check across all chunks
        for ev in doc_evidence:
            ev_lower = ev.snippet.lower()
            if supp_lower in ev_lower and buyer_lower in ev_lower and mat_lower in ev_lower:
                return ev

    return None


def process_document(doc_id: int, db: Session) -> bool:
    """
    Processes a procurement document by ID:
    - Sets extraction_status = 'processing' and commits separately.
    - In an atomic transaction:
      1. Parses document file via parse_document.
      2. Saves parsed raw_text and page_count to Document.
      3. Idempotently creates/updates Evidence records from parsed chunks,
         strictly preserving existing Evidence records linked to relationships.
      4. Extracts structured supplier relationship candidates.
      5. Resolves supplier and material entities via EntityResolver.
      6. Creates relationships with status='pending' and tier=None,
         anchored to the matched Evidence records.
      7. Sets extraction_status = 'done' and commits.
    - On failure:
      Rolls back partial processing changes and safely sets extraction_status = 'failed'
      in a fresh usable transaction.

    Args:
        doc_id: Primary key ID of the Document to process.
        db: SQLAlchemy database session.

    Returns:
        bool: True if document was successfully processed, False otherwise.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        logger.warning(f"Document {doc_id} not found for processing.")
        return False

    # 1. Initial processing-status commit in its own separate transaction
    doc.extraction_status = "processing"
    db.commit()

    try:
        parsed: ParsedDocument = parse_document(doc.file_path, doc_type=doc.doc_type)

        # Update document text and page count
        doc.raw_text = parsed.raw_text
        doc.page_count = parsed.page_count

        # ---------------------------------------------------------------------
        # 2. Evidence Synchronization (Preserving Linked Foreign Keys)
        # ---------------------------------------------------------------------
        existing_evidence = (
            db.query(Evidence)
            .filter(Evidence.document_id == doc.id)
            .all()
        )
        existing_map: Dict[Tuple[Optional[int], Optional[int]], Evidence] = {
            (ev.page, ev.chunk_index): ev for ev in existing_evidence
        }

        # Identify evidence records referenced by any Relationship
        existing_ev_ids = [ev.id for ev in existing_evidence]
        linked_ev_ids: Set[int] = set()

        if existing_ev_ids:
            primary_linked = (
                db.query(Relationship.evidence_id)
                .filter(Relationship.evidence_id.in_(existing_ev_ids))
                .all()
            )
            for (pe_id,) in primary_linked:
                if pe_id is not None:
                    linked_ev_ids.add(pe_id)

            junction_linked = (
                db.query(RelationshipEvidence.evidence_id)
                .filter(RelationshipEvidence.evidence_id.in_(existing_ev_ids))
                .all()
            )
            for (je_id,) in junction_linked:
                if je_id is not None:
                    linked_ev_ids.add(je_id)

        seen_keys: Set[Tuple[Optional[int], Optional[int]]] = set()

        for chunk in parsed.chunks:
            key = (chunk.page, chunk.chunk_index)
            seen_keys.add(key)

            if key in existing_map:
                # Update snippet in place preserving Evidence.id and foreign keys
                ev = existing_map[key]
                ev.snippet = chunk.snippet
            else:
                # Insert new Evidence record
                new_ev = Evidence(
                    document_id=doc.id,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    snippet=chunk.snippet,
                    llm_confidence=None,
                )
                db.add(new_ev)

        # Safely handle existing evidence no longer present in parsed chunks
        for key, ev in existing_map.items():
            if key not in seen_keys:
                if ev.id in linked_ev_ids:
                    logger.info(
                        f"Preserving linked Evidence {ev.id} for document {doc.id} during reprocessing."
                    )
                else:
                    db.delete(ev)

        # Flush evidence changes so that all Evidence records have an ID assigned
        db.flush()

        # Load all active evidence records for this document
        doc_evidence: List[Evidence] = (
            db.query(Evidence)
            .filter(Evidence.document_id == doc.id)
            .order_by(Evidence.page.asc(), Evidence.chunk_index.asc())
            .all()
        )

        # ---------------------------------------------------------------------
        # 3. AI / Pattern Relationship Extraction
        # ---------------------------------------------------------------------
        extraction_result = extract_relationships(
            text=parsed.raw_text,
            filename=doc.filename,
            page=None,
        )

        # ---------------------------------------------------------------------
        # 4. Entity Resolution & Idempotent Relationship Linkage
        # ---------------------------------------------------------------------
        for candidate in extraction_result.relationships:
            # Safeguard 1 & 2: Match candidate to a valid Evidence chunk
            matching_ev = _find_best_matching_evidence(doc_evidence, candidate)
            if matching_ev is None:
                logger.warning(
                    f"Skipping candidate relationship '{candidate.supplier} -> {candidate.buyer}' "
                    f"({candidate.material}) in document {doc.id}: no matching evidence chunk found."
                )
                continue

            # Update evidence confidence if higher or null
            if candidate.confidence is not None:
                if matching_ev.llm_confidence is None or candidate.confidence > matching_ev.llm_confidence:
                    matching_ev.llm_confidence = candidate.confidence

            # Resolve entities
            supp_res = entity_resolver.resolve_supplier(db, candidate.supplier, allow_create=True)
            buyer_res = entity_resolver.resolve_supplier(db, candidate.buyer, allow_create=True)
            mat_res = entity_resolver.resolve_material(db, candidate.material, allow_create=True)

            # Safeguard 4: Create relationship ONLY when both parties and material are resolved
            if not (supp_res.is_resolved and supp_res.entity_id):
                logger.warning(
                    f"Skipping candidate relationship in doc {doc.id}: supplier '{candidate.supplier}' "
                    f"could not be resolved (ambiguous: {supp_res.is_ambiguous})."
                )
                continue

            if not (buyer_res.is_resolved and buyer_res.entity_id):
                logger.warning(
                    f"Skipping candidate relationship in doc {doc.id}: buyer '{candidate.buyer}' "
                    f"could not be resolved (ambiguous: {buyer_res.is_ambiguous})."
                )
                continue

            if not (mat_res.is_resolved and mat_res.entity_id):
                logger.warning(
                    f"Skipping candidate relationship in doc {doc.id}: material '{candidate.material}' "
                    f"could not be resolved (ambiguous: {mat_res.is_ambiguous})."
                )
                continue

            # Check self-supply constraint (check_rel_no_self_supply)
            if supp_res.entity_id == buyer_res.entity_id:
                logger.warning(
                    f"Skipping candidate relationship in doc {doc.id}: self-supply detected "
                    f"(supplier_id == buyer_id == {supp_res.entity_id})."
                )
                continue

            # Safeguard 3: Inspect existing uniqueness constraint (supplier_id, buyer_id, material_id)
            existing_rel = (
                db.query(Relationship)
                .filter_by(
                    supplier_id=supp_res.entity_id,
                    buyer_id=buyer_res.entity_id,
                    material_id=mat_res.entity_id,
                )
                .first()
            )

            if not existing_rel:
                # Create new relationship: strictly 'pending' status and tier is NULL
                new_rel = Relationship(
                    supplier_id=supp_res.entity_id,
                    buyer_id=buyer_res.entity_id,
                    material_id=mat_res.entity_id,
                    tier=None,  # Preserved as NULL until graph rebuild
                    lead_time_days=candidate.lead_time_days,
                    share_pct=candidate.share_pct,
                    inventory_days=0,
                    quantity_per_month=candidate.quantity_per_month,
                    confidence=candidate.confidence,
                    status="pending",  # Never auto-approved
                    evidence_id=matching_ev.id,
                )
                db.add(new_rel)
                db.flush()

                # Link primary evidence in junction table
                db.add(
                    RelationshipEvidence(
                        relationship_id=new_rel.id,
                        evidence_id=matching_ev.id,
                    )
                )
                db.flush()
                logger.info(
                    f"Created pending relationship {new_rel.id}: "
                    f"'{supp_res.canonical_name}' -> '{buyer_res.canonical_name}' "
                    f"('{mat_res.canonical_name}') from document {doc.id} (evidence: {matching_ev.id}, page: {matching_ev.page})"
                )
            else:
                # Existing relationship: preserve existing status and tier!
                if existing_rel.status == "pending":
                    # Backfill missing metadata if available
                    if existing_rel.lead_time_days is None and candidate.lead_time_days is not None:
                        existing_rel.lead_time_days = candidate.lead_time_days
                    if existing_rel.share_pct is None and candidate.share_pct is not None:
                        existing_rel.share_pct = candidate.share_pct
                    if existing_rel.quantity_per_month is None and candidate.quantity_per_month is not None:
                        existing_rel.quantity_per_month = candidate.quantity_per_month
                    if existing_rel.confidence is None or (
                        candidate.confidence is not None and candidate.confidence > existing_rel.confidence
                    ):
                        existing_rel.confidence = candidate.confidence

                # If primary evidence_id was null, attach it
                if existing_rel.evidence_id is None:
                    existing_rel.evidence_id = matching_ev.id

                # Idempotently attach new evidence chunk in junction table if not already linked
                existing_junction = (
                    db.query(RelationshipEvidence)
                    .filter_by(
                        relationship_id=existing_rel.id,
                        evidence_id=matching_ev.id,
                    )
                    .first()
                )
                if not existing_junction:
                    db.add(
                        RelationshipEvidence(
                            relationship_id=existing_rel.id,
                            evidence_id=matching_ev.id,
                        )
                    )
                    db.flush()
                    logger.info(
                        f"Linked new Evidence {matching_ev.id} to existing Relationship {existing_rel.id} (status: {existing_rel.status})"
                    )

        # ---------------------------------------------------------------------
        # 5. Commit Successful Processing
        # ---------------------------------------------------------------------
        doc.extraction_status = "done"
        db.commit()
        return True

    except Exception as e:
        logger.exception(f"Error processing document {doc_id}: {e}")
        # Roll back all uncommitted processing changes
        db.rollback()

        # Safely record failed status in a fresh usable transaction
        try:
            failed_doc = db.query(Document).filter(Document.id == doc_id).first()
            if failed_doc:
                failed_doc.extraction_status = "failed"
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Failed to record 'failed' status for document {doc_id}: {rollback_err}")
            db.rollback()

        return False
