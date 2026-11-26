"""
AI-powered and pattern-based supplier relationship extraction service for TierLens AI (Milestone 4: TASK-023).
Extracts structured supplier relationships, materials, quantities, lead times, and verbatim evidence snippets
from procurement text. Conforms to ARCHITECTURE.md Section 3.2 and API_SPEC.md Section 4.2.
"""

import os
import json
import logging
import re
from typing import Optional, List, Dict, Any, Union

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.models.schemas import ExtractionRelationshipItem, ExtractionResult

logger = logging.getLogger(__name__)

GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def extract_relationships(
    text: str,
    filename: Optional[str] = None,
    page: Optional[int] = 1,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> ExtractionResult:
    """
    Extracts structured procurement relationships from raw text.
    If an API key is available (passed explicitly or configured in settings.GEMINI_API_KEY),
    calls the Gemini REST API with structured JSON output instructions.
    If no API key is provided, falls back to deterministic procurement pattern extraction.

    Args:
        text: Raw text content from document or chunk.
        filename: Optional source document filename.
        page: 1-based page number (defaults to 1).
        api_key: Optional Gemini API key override.
        model: Optional model name override (defaults to settings.LLM_MODEL).
        client: Optional httpx.Client instance for dependency injection and testing.

    Returns:
        ExtractionResult containing validated ExtractionRelationshipItem objects.
    """
    if not text or not text.strip():
        return ExtractionResult(relationships=[], entities_found=0)

    effective_key = api_key if api_key is not None else (os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY)
    effective_model = model or os.getenv("LLM_MODEL") or settings.LLM_MODEL or "gemini-2.5-flash"

    # Live Gemini extraction if API key is present
    if effective_key and effective_key.strip():
        return _extract_with_gemini(
            text=text,
            filename=filename,
            page=page,
            api_key=effective_key.strip(),
            model=effective_model,
            client=client,
        )

    # Deterministic pattern-based fallback extraction
    return _extract_with_fallback(text=text, filename=filename, page=page)


# =============================================================================
# Live Gemini Extraction
# =============================================================================

def normalize_confidence(conf: Any) -> Optional[float]:
    """
    Normalizes and validates extraction confidence scores:
    - Values in [0.0, 1.0] remain unchanged.
    - Values greater than 1.0 and at most 100.0 are interpreted as percentages and divided by 100.
    - Values below 0.0 or above 100.0 are rejected as invalid (returns None).
    - Non-numeric or None values are rejected as invalid (returns None).
    """
    if conf is None:
        return None
    try:
        val = float(conf)
    except (ValueError, TypeError):
        return None
    if 0.0 <= val <= 1.0:
        return val
    if 1.0 < val <= 100.0:
        return val / 100.0
    return None


def _extract_with_gemini(
    text: str,
    filename: Optional[str],
    page: Optional[int],
    api_key: str,
    model: str,
    client: Optional[httpx.Client] = None,
) -> ExtractionResult:
    """
    Executes live structured extraction via Google's Gemini REST API using httpx.
    Safely transmits the API key via headers to prevent URL logging leakage.
    """
    url = GEMINI_API_URL_TEMPLATE.format(model=model)
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    prompt = (
        "You are an expert procurement and supply chain intelligence extraction engine.\n"
        "Analyze the following procurement document text and extract all supplier relationships.\n\n"
        "For each relationship, extract:\n"
        "- supplier: The upstream supplier entity name\n"
        "- buyer: The downstream purchasing entity name\n"
        "- material: The specific material, part, or component being supplied\n"
        "- lead_time_days: Integer number of days for lead time, or null if not stated\n"
        "- share_pct: Float (0-100) percentage share of buyer's demand, or null if not stated\n"
        "- quantity_per_month: Float monthly volume/quantity, or null if not stated\n"
        "- confidence: Float (0.0 to 1.0) reflecting your extraction certainty\n"
        "- snippet: An EXACT, verbatim quote from the text supporting this relationship\n"
        "- page: Integer page number\n\n"
        "Strict rules:\n"
        "1. Never invent or hallucinate facts missing from the source text.\n"
        "2. The snippet must be an exact verbatim substring from the source text.\n"
        "3. Confidence must be between 0.0 and 1.0.\n"
        "4. If no supplier relationship exists, return an empty relationships list.\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "relationships": [\n'
        "    {\n"
        '      "supplier": "string",\n'
        '      "buyer": "string",\n'
        '      "material": "string",\n'
        '      "lead_time_days": null,\n'
        '      "share_pct": null,\n'
        '      "quantity_per_month": null,\n'
        '      "confidence": 0.95,\n'
        '      "source_doc": "string or null",\n'
        '      "snippet": "verbatim text quote",\n'
        '      "page": 1\n'
        "    }\n"
        "  ],\n"
        '  "entities_found": 2\n'
        "}\n\n"
        f"DOCUMENT TEXT:\n{text}\n"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }

    try:
        if client is not None:
            response = client.post(url, headers=headers, json=payload, timeout=15.0)
        else:
            with httpx.Client(timeout=15.0) as default_client:
                response = default_client.post(url, headers=headers, json=payload)

        response.raise_for_status()
        data = response.json()

        # Extract generated text from Gemini response structure
        candidates = data.get("candidates", [])
        if not candidates:
            logger.warning("Gemini returned no candidates in response.")
            return ExtractionResult(relationships=[], entities_found=0)

        raw_parts = candidates[0].get("content", {}).get("parts", [])
        if not raw_parts:
            return ExtractionResult(relationships=[], entities_found=0)

        raw_text = raw_parts[0].get("text", "").strip()

        # Strip markdown code fences if present
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

        parsed_json = json.loads(cleaned_text)

        # Validate and normalize confidence values prior to schema validation
        # Reject relationships with invalid confidence (< 0 or > 100 or non-numeric)
        valid_rels = []
        if isinstance(parsed_json, dict) and "relationships" in parsed_json:
            for rel_dict in parsed_json.get("relationships", []):
                if isinstance(rel_dict, dict) and "confidence" in rel_dict:
                    normalized_conf = normalize_confidence(rel_dict["confidence"])
                    if normalized_conf is None:
                        logger.warning(
                            f"Rejecting extracted relationship due to invalid confidence value: {rel_dict.get('confidence')}"
                        )
                        continue
                    rel_dict["confidence"] = normalized_conf
                    valid_rels.append(rel_dict)
                else:
                    valid_rels.append(rel_dict)
            parsed_json["relationships"] = valid_rels

        result = ExtractionResult.model_validate(parsed_json)

        # Post-validate and attach defaults
        validated_items: List[ExtractionRelationshipItem] = []
        for item in result.relationships:
            if not item.source_doc and filename:
                item.source_doc = filename
            if not item.page and page:
                item.page = page

            # Ensure snippet is non-empty
            if not item.snippet or not item.snippet.strip():
                # Fallback to first line containing both parties if available
                matching_lines = [l.strip() for l in text.splitlines() if item.supplier in l and item.buyer in l]
                item.snippet = matching_lines[0] if matching_lines else text.strip()[:200]

            validated_items.append(item)

        entities_count = result.entities_found
        if entities_count is None:
            distinct_entities = set()
            for r in validated_items:
                distinct_entities.add(r.supplier)
                distinct_entities.add(r.buyer)
                distinct_entities.add(r.material)
            entities_count = len(distinct_entities)

        return ExtractionResult(relationships=validated_items, entities_found=entities_count)

    except httpx.TimeoutException as te:
        logger.warning(f"Timeout connecting to Gemini extraction API: {te}")
        return ExtractionResult(relationships=[], entities_found=0)
    except httpx.HTTPStatusError as hse:
        logger.warning(f"HTTP error {hse.response.status_code} from Gemini extraction API.")
        return ExtractionResult(relationships=[], entities_found=0)
    except httpx.RequestError as re_err:
        logger.warning(f"Network request error contacting Gemini API: {re_err}")
        return ExtractionResult(relationships=[], entities_found=0)
    except (json.JSONDecodeError, ValidationError) as parse_err:
        logger.warning(f"Failed to parse or validate Gemini extraction output: {parse_err}")
        return ExtractionResult(relationships=[], entities_found=0)
    except Exception as exc:
        logger.exception(f"Unexpected error during live Gemini extraction: {exc}")
        return ExtractionResult(relationships=[], entities_found=0)


# =============================================================================
# Offline Deterministic Fallback Extraction
# =============================================================================

def _normalize_material_name(raw_material: str) -> str:
    """Normalizes raw material text to standard canonical names matching sample data."""
    m = raw_material.strip().lower()
    if "latex" in m:
        return "Natural Latex"
    if "carbon" in m:
        return "Carbon Black"
    if "rubber" in m and ("compound" in m or "processed" in m or "vulcanized" in m or "specialty" in m):
        return "Processed Rubber"
    if "tyre" in m or "tire" in m:
        return "Tyres"
    if "seal" in m or "gasket" in m:
        return "Rubber Seals"
    return raw_material.strip().title()


def _normalize_party_name(party: str) -> str:
    """Normalizes party names to standard canonical names without hardcoding IDs."""
    p = party.strip()
    # Strip common document prefix tokens if captured by regex
    p = re.sub(r"^(?:PURCHASE ORDER(?:\s+[A-Za-z0-9_]+)?:\s*|\[DEMONSTRATION SAMPLE\]\s*(?:Procurement Note|Supply Agreement):\s*)", "", p, flags=re.IGNORECASE)
    # Strip trailing facility or plant location qualifiers
    p = re.sub(r"\s+(?:Pune|Mumbai|Chennai)\s+(?:Assembly\s+Plant|Plant|Facility)$", "", p, flags=re.IGNORECASE)
    # Specific known abbreviations in synthetic texts
    if p.lower() == "rubbercore":
        return "RubberCore Industries"
    return p.strip()


def _parse_lead_time_days(text: str) -> Optional[int]:
    """Extracts lead time in days if explicitly stated in text."""
    m = re.search(r"(\d+)\s*days?(?:\s+standard)?\s+lead\s+time", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:standard\s+)?lead\s+time:\s*(\d+)\s*days?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _parse_quantity_monthly(text: str) -> Optional[float]:
    """Extracts monthly quantity or volume if explicitly stated in text."""
    # Pattern: 'Monthly Volume: 150 MT' or 'Quantity: 4,000 units'
    m = re.search(r"(?:Monthly Volume|Quantity):\s*([\d,]+(?:\.\d+)?)\s*(?:MT|units)?", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    # Pattern: 'to supply 40 MT of natural latex'
    m = re.search(r"to\s+supply\s+([\d,]+(?:\.\d+)?)\s*MT", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    # Pattern: 'with 35 MT monthly supply'
    m = re.search(r"with\s+([\d,]+(?:\.\d+)?)\s*MT\s+monthly\s+supply", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _extract_with_fallback(
    text: str,
    filename: Optional[str] = None,
    page: Optional[int] = 1,
) -> ExtractionResult:
    """
    Deterministic regex pattern extractor supporting standard procurement formulations
    and the six synthetic sample business documents.
    Extracts only facts directly supported by the text and returns an empty list
    for unrelated or unsupported text.
    """
    supplier: Optional[str] = None
    buyer: Optional[str] = None
    material: Optional[str] = None
    verbatim_snippet: Optional[str] = None

    # Pattern 1: Explicit key-value labels (Contracts & Procurement Notes)
    # Supports single-line (Buyer first or Supplier first) and multi-line separated by paragraph/blank lines
    # e.g. "Buyer: TyreWorks Ltd, Supplier: RubberCore Industries, Material: Processed Rubber."
    # or "Supplier: BluePeak Chemicals Pvt Ltd\n\nBuyer: RubberCore Industries\n\nMaterial: Synthetic Rubber"
    m_explicit_single = re.search(
        r"(?:Buyer:\s*([^,\r\n]+),\s*Supplier:\s*([^,\r\n]+),\s*Material:\s*([^\.\r\n]+)|"
        r"Supplier:\s*([^,\r\n]+),\s*Buyer:\s*([^,\r\n]+),\s*Material:\s*([^\.\r\n]+))",
        text,
        re.IGNORECASE,
    )
    if m_explicit_single:
        if m_explicit_single.group(1):
            buyer = _normalize_party_name(m_explicit_single.group(1))
            supplier = _normalize_party_name(m_explicit_single.group(2))
            material = _normalize_material_name(m_explicit_single.group(3))
        else:
            supplier = _normalize_party_name(m_explicit_single.group(4))
            buyer = _normalize_party_name(m_explicit_single.group(5))
            material = _normalize_material_name(m_explicit_single.group(6))
        verbatim_snippet = m_explicit_single.group(0).strip()
    else:
        m_explicit_multi = re.search(
            r"(?:Supplier:\s*([^\r\n,\.]+)\s*[\r\n]+\s*[\r\n]+\s*Buyer:\s*([^\r\n,\.]+)|"
            r"Buyer:\s*([^\r\n,\.]+)\s*[\r\n]+\s*[\r\n]+\s*Supplier:\s*([^\r\n,\.]+))\s*[\r\n]+\s*[\r\n]+\s*"
            r"Material:\s*([^\r\n\.]+)",
            text,
            re.IGNORECASE,
        )
        if m_explicit_multi:
            if m_explicit_multi.group(1):
                supplier = _normalize_party_name(m_explicit_multi.group(1))
                buyer = _normalize_party_name(m_explicit_multi.group(2))
            else:
                buyer = _normalize_party_name(m_explicit_multi.group(3))
                supplier = _normalize_party_name(m_explicit_multi.group(4))
            material = _normalize_material_name(m_explicit_multi.group(5))

            matching_lines = [
                l.strip() for l in text.splitlines()
                if supplier in l and (buyer in l or material in l)
            ]
            if not matching_lines:
                matching_lines = [
                    l.strip() for l in text.splitlines()
                    if supplier in l or buyer in l
                ]
            verbatim_snippet = matching_lines[0] if matching_lines else m_explicit_multi.group(0).strip()

    # Pattern 2: Supply agreement / Purchase order statement
    # Recognizes both 'to supply' and 'supplies'
    # e.g. "GreenLatex Pvt Ltd to supply 40 MT of natural latex to RubberCore Industries monthly"
    # or "BluePeak Chemicals Pvt Ltd supplies Synthetic Rubber to RubberCore Industries."
    if not supplier or not buyer or not material:
        m_supply = re.search(
            r"([A-Za-z0-9\.\s]+?)\s+(?:to\s+supply|supplies)\s+(?:\d+[\d,\.]*\s*MT\s+of\s+)?([A-Za-z\s]+?)\s+to\s+([A-Za-z0-9\.\s]+?)(?:\s+monthly|\.|\r|\n|$)",
            text,
            re.IGNORECASE,
        )
        if m_supply:
            raw_supp = m_supply.group(1).strip()
            # Clean possible leading prefix
            supplier = _normalize_party_name(raw_supp)
            material = _normalize_material_name(m_supply.group(2))
            buyer = _normalize_party_name(m_supply.group(3))
            # Extract line containing this match as snippet
            lines = [l.strip() for l in text.splitlines() if raw_supp in l and m_supply.group(3).strip() in l]
            verbatim_snippet = lines[0] if lines else m_supply.group(0).strip()

    # Pattern 3: Delivery statement (Purchase orders)
    # "TyreWorks Ltd delivers automotive tyre assemblies to AutoMotive Corp Pune Assembly Plant"
    if not supplier or not buyer or not material:
        m_deliver = re.search(
            r"([A-Za-z0-9\.\s]+?)\s+delivers\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z0-9\.\s]+?)(?:\s+Pune|\s+Assembly|\.|\n|$)",
            text,
            re.IGNORECASE,
        )
        if m_deliver:
            raw_supp = m_deliver.group(1).strip()
            supplier = _normalize_party_name(raw_supp)
            material = _normalize_material_name(m_deliver.group(2))
            buyer = _normalize_party_name(m_deliver.group(3))
            lines = [l.strip() for l in text.splitlines() if raw_supp in l and "delivers" in l]
            verbatim_snippet = lines[0] if lines else m_deliver.group(0).strip()

    # Pattern 4: Sourcing note (Procurement notes)
    # "RubberCore sourcing carbon black from PetroChem Asia as primary supplier"
    if not supplier or not buyer or not material:
        m_sourcing = re.search(
            r"([A-Za-z0-9\.\s]+?)\s+sourcing\s+([A-Za-z\s]+?)\s+from\s+([A-Za-z0-9\.\s]+?)(?:\s+as\s+primary|\.|\n|$)",
            text,
            re.IGNORECASE,
        )
        if m_sourcing:
            buyer = _normalize_party_name(m_sourcing.group(1))
            material = _normalize_material_name(m_sourcing.group(2))
            supplier = _normalize_party_name(m_sourcing.group(3))
            lines = [l.strip() for l in text.splitlines() if m_sourcing.group(3).strip() in l and "sourcing" in l]
            verbatim_snippet = lines[0] if lines else m_sourcing.group(0).strip()

    # If no reliable relationship is found, return empty result
    if not supplier or not buyer or not material or supplier == buyer:
        return ExtractionResult(relationships=[], entities_found=0)

    # Ensure verbatim snippet actually exists in text
    if not verbatim_snippet or verbatim_snippet not in text:
        matching_lines = [l.strip() for l in text.splitlines() if supplier in l or material in l]
        verbatim_snippet = matching_lines[0] if matching_lines else text.strip()[:200]

    lead_time_days = _parse_lead_time_days(text)
    quantity_monthly = _parse_quantity_monthly(text)

    # Share pct is null unless explicitly stated
    # Supports "30% share", "30% allocation", "Supply Share: 30%", "Share: 30%"
    share_pct: Optional[float] = None
    m_share = re.search(
        r"(?:(?:supply\s+)?(?:share|allocation):\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*(?:share|allocation))",
        text,
        re.IGNORECASE,
    )
    if m_share:
        raw_val = m_share.group(1) or m_share.group(2)
        if raw_val is not None:
            share_pct = float(raw_val)

    item = ExtractionRelationshipItem(
        supplier=supplier,
        buyer=buyer,
        material=material,
        lead_time_days=lead_time_days,
        share_pct=share_pct,
        quantity_per_month=quantity_monthly,
        confidence=0.95,
        source_doc=filename,
        snippet=verbatim_snippet,
        page=page or 1,
    )

    entities = {supplier, buyer, material}
    return ExtractionResult(relationships=[item], entities_found=len(entities))
