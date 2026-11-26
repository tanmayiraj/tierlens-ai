"""
Unit tests for Structured Supplier Relationship Extraction Engine (Milestone 4: TASK-023).
Tests both deterministic pattern-based fallback extraction across the six synthetic sample documents
and live Gemini API interaction using mocked HTTP responses without network access.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from backend.config import settings
from backend.services.document_parser import parse_document
from backend.services.llm_extractor import extract_relationships, normalize_confidence
from backend.models.schemas import ExtractionResult, ExtractionRelationshipItem

SAMPLE_DOCS_DIR = Path("data/sample_docs")


# =============================================================================
# Fallback Extraction Tests across Synthetic Sample Documents
# =============================================================================

def test_extract_sample_po_1042():
    """Verifies fallback extraction on PO_1042.pdf (GreenLatex -> RubberCore)."""
    doc_path = SAMPLE_DOCS_DIR / "PO_1042.pdf"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="PO_1042.pdf", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "GreenLatex Pvt Ltd"
    assert rel.buyer == "RubberCore Industries"
    assert rel.material == "Natural Latex"
    assert rel.quantity_per_month == 40.0
    assert rel.lead_time_days == 21
    assert rel.source_doc == "PO_1042.pdf"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


def test_extract_sample_contract_rubbercore_tyreworks():
    """Verifies fallback extraction on Contract_RubberCore_TyreWorks.txt (RubberCore -> TyreWorks)."""
    doc_path = SAMPLE_DOCS_DIR / "Contract_RubberCore_TyreWorks.txt"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="Contract_RubberCore_TyreWorks.txt", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "RubberCore Industries"
    assert rel.buyer == "TyreWorks Ltd"
    assert rel.material == "Processed Rubber"
    assert rel.quantity_per_month == 150.0
    assert rel.lead_time_days == 10
    assert rel.source_doc == "Contract_RubberCore_TyreWorks.txt"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


def test_extract_sample_contract_rubbercore_gripseal():
    """Verifies fallback extraction on Contract_RubberCore_GripSeal.txt (RubberCore -> GripSeal)."""
    doc_path = SAMPLE_DOCS_DIR / "Contract_RubberCore_GripSeal.txt"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="Contract_RubberCore_GripSeal.txt", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "RubberCore Industries"
    assert rel.buyer == "GripSeal Components"
    assert rel.material == "Processed Rubber"
    assert rel.quantity_per_month == 50.0
    assert rel.lead_time_days == 10
    assert rel.source_doc == "Contract_RubberCore_GripSeal.txt"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


def test_extract_sample_po_tyreworks_automotive():
    """Verifies fallback extraction on PO_TyreWorks_AutoMotive.pdf (TyreWorks -> AutoMotive Corp)."""
    doc_path = SAMPLE_DOCS_DIR / "PO_TyreWorks_AutoMotive.pdf"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="PO_TyreWorks_AutoMotive.pdf", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "TyreWorks Ltd"
    assert rel.buyer == "AutoMotive Corp"
    assert rel.material == "Tyres"
    assert rel.quantity_per_month == 4000.0
    assert rel.lead_time_days is None
    assert rel.source_doc == "PO_TyreWorks_AutoMotive.pdf"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


def test_extract_sample_po_gripseal_automotive():
    """Verifies fallback extraction on PO_GripSeal_AutoMotive.pdf (GripSeal -> AutoMotive Corp)."""
    doc_path = SAMPLE_DOCS_DIR / "PO_GripSeal_AutoMotive.pdf"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="PO_GripSeal_AutoMotive.pdf", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "GripSeal Components"
    assert rel.buyer == "AutoMotive Corp"
    assert rel.material == "Rubber Seals"
    assert rel.quantity_per_month == 2500.0
    assert rel.lead_time_days is None
    assert rel.source_doc == "PO_GripSeal_AutoMotive.pdf"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


def test_extract_sample_procurement_note_07():
    """Verifies fallback extraction on Procurement_Note_07.txt (PetroChem Asia -> RubberCore)."""
    doc_path = SAMPLE_DOCS_DIR / "Procurement_Note_07.txt"
    parsed = parse_document(doc_path)

    result = extract_relationships(text=parsed.raw_text, filename="Procurement_Note_07.txt", page=1, api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "PetroChem Asia"
    assert rel.buyer == "RubberCore Industries"
    assert rel.material == "Carbon Black"
    assert rel.quantity_per_month == 35.0
    assert rel.lead_time_days == 14
    assert rel.source_doc == "Procurement_Note_07.txt"
    assert rel.page == 1
    assert 0.0 <= rel.confidence <= 1.0
    assert rel.snippet in parsed.raw_text


# =============================================================================
# Edge Cases and Fallback Behavior
# =============================================================================

def test_extract_unrelated_text_returns_empty():
    """Verifies that non-procurement text yields an empty relationship list without errors."""
    unrelated_text = (
        "Internal Facilities Notice: The quarterly air-conditioning maintenance "
        "will take place this Saturday between 9:00 AM and 1:00 PM. Please power down "
        "all non-essential computer monitors before leaving on Friday."
    )
    result = extract_relationships(text=unrelated_text, filename="Notice.txt", api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 0
    assert result.entities_found == 0


def test_extract_empty_or_whitespace_text():
    """Verifies that empty string or whitespace returns empty ExtractionResult."""
    assert len(extract_relationships(text="", filename="empty.txt").relationships) == 0
    assert len(extract_relationships(text="   \n\t  ", filename="blank.txt").relationships) == 0


def test_extract_missing_api_key_uses_fallback(monkeypatch):
    """Verifies that when settings.GEMINI_API_KEY is None, fallback extractor runs cleanly."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    sample_text = "Purchase Order PO_1042: GreenLatex Pvt Ltd to supply 40 MT of natural latex to RubberCore Industries monthly."
    result = extract_relationships(text=sample_text, filename="PO_1042.pdf")

    assert len(result.relationships) == 1
    assert result.relationships[0].supplier == "GreenLatex Pvt Ltd"


# =============================================================================
# Mocked Gemini API Tests (No Real Network Calls)
# =============================================================================

def test_mocked_gemini_api_success():
    """Verifies live mode successfully parses and validates mock Gemini JSON response."""
    mock_payload = {
        "relationships": [
            {
                "supplier": "Alpha Minerals Inc",
                "buyer": "Beta Steelworks",
                "material": "Iron Ore",
                "lead_time_days": 18,
                "share_pct": 65.0,
                "quantity_per_month": 500.0,
                "confidence": 0.94,
                "source_doc": "Supply_Agreement_01.pdf",
                "snippet": "Alpha Minerals Inc to supply 500 MT Iron Ore to Beta Steelworks.",
                "page": 1,
            }
        ],
        "entities_found": 3,
    }

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": f"```json\n{json.dumps(mock_payload)}\n```"}
                    ]
                }
            }
        ]
    }

    # Create mock httpx client
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_response
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    input_text = "Alpha Minerals Inc to supply 500 MT Iron Ore to Beta Steelworks with 18 days lead time."
    result = extract_relationships(
        text=input_text,
        filename="Supply_Agreement_01.pdf",
        api_key="mock_secret_key",
        client=mock_client,
    )

    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.supplier == "Alpha Minerals Inc"
    assert rel.buyer == "Beta Steelworks"
    assert rel.material == "Iron Ore"
    assert rel.lead_time_days == 18
    assert rel.share_pct == 65.0
    assert rel.quantity_per_month == 500.0
    assert rel.confidence == 0.94
    assert result.entities_found == 3

    # Verify that the API key was passed in headers and NOT exposed in URL
    call_args = mock_client.post.call_args
    assert "mock_secret_key" not in call_args[0][0]  # URL does NOT have key
    assert call_args[1]["headers"]["x-goog-api-key"] == "mock_secret_key"


def test_mocked_gemini_api_invalid_json():
    """Verifies that malformed or non-JSON response from Gemini is handled gracefully."""
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "I am unable to parse this document: ERROR 400 MALFORMED_OUTPUT"}
                    ]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_response
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    result = extract_relationships(
        text="Sample text",
        api_key="mock_key",
        client=mock_client,
    )

    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 0
    assert result.entities_found == 0


def test_mocked_gemini_api_http_error():
    """Verifies that HTTP 500/502 from Gemini API is handled gracefully without crashing."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 502
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Bad Gateway",
        request=MagicMock(),
        response=mock_response,
    )
    mock_client.post.return_value = mock_response

    result = extract_relationships(
        text="Sample text",
        api_key="mock_key",
        client=mock_client,
    )

    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 0
    assert result.entities_found == 0


def test_mocked_gemini_api_timeout():
    """Verifies that an httpx TimeoutException is handled gracefully."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Read timeout after 15.0s")

    result = extract_relationships(
        text="Sample text",
        api_key="mock_key",
        client=mock_client,
    )

    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 0
    assert result.entities_found == 0


def test_normalize_confidence_unit():
    """Verifies normalize_confidence logic across exact decimals, percentages, and invalid values."""
    assert normalize_confidence(0.15) == pytest.approx(0.15)
    assert normalize_confidence(0.85) == pytest.approx(0.85)
    assert normalize_confidence(1.0) == pytest.approx(1.0)
    assert normalize_confidence(0.0) == pytest.approx(0.0)
    assert normalize_confidence(15) == pytest.approx(0.15)
    assert normalize_confidence(85) == pytest.approx(0.85)
    assert normalize_confidence(100.0) == pytest.approx(1.0)
    assert normalize_confidence("85") == pytest.approx(0.85)
    assert normalize_confidence("0.85") == pytest.approx(0.85)

    # Invalid: negative values
    assert normalize_confidence(-0.1) is None
    assert normalize_confidence(-5) is None

    # Invalid: values greater than 100
    assert normalize_confidence(100.1) is None
    assert normalize_confidence(150) is None

    # Invalid: non-numeric
    assert normalize_confidence("not-a-number") is None
    assert normalize_confidence(None) is None


def test_extraction_relationship_item_confidence_validator():
    """Verifies schema validation on ExtractionRelationshipItem for confidence scaling and rejection."""
    # Valid values
    item_dec = ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=0.85)
    assert item_dec.confidence == pytest.approx(0.85)

    item_low_dec = ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=0.15)
    assert item_low_dec.confidence == pytest.approx(0.15)

    item_one = ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=1.0)
    assert item_one.confidence == pytest.approx(1.0)

    # Percentage integers scaled down
    item_pct = ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=85)
    assert item_pct.confidence == pytest.approx(0.85)

    item_low_pct = ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=15)
    assert item_low_pct.confidence == pytest.approx(0.15)

    # Negative values rejected
    with pytest.raises(ValidationError):
        ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=-0.5)

    # Greater than 100 rejected
    with pytest.raises(ValidationError):
        ExtractionRelationshipItem(supplier="A", buyer="B", material="C", snippet="s", confidence=120)


def test_confidence_validation_and_scaling_in_gemini_extraction():
    """Verifies that percentages (15, 85) are scaled down, decimals (0.15, 0.85, 1.0) preserved, and invalid rejected."""
    mock_payload = {
        "relationships": [
            {
                "supplier": "Vendor A",
                "buyer": "Buyer B",
                "material": "Material 1",
                "confidence": 85,  # Percentage -> 0.85
                "snippet": "Vendor A supplies Material 1 to Buyer B",
                "page": 1,
            },
            {
                "supplier": "Vendor C",
                "buyer": "Buyer D",
                "material": "Material 2",
                "confidence": 0.15,  # Exact decimal
                "snippet": "Vendor C supplies Material 2 to Buyer D",
                "page": 1,
            },
            {
                "supplier": "Vendor E",
                "buyer": "Buyer F",
                "material": "Material 3",
                "confidence": -10,  # Negative -> must be rejected
                "snippet": "Vendor E supplies Material 3 to Buyer F",
                "page": 1,
            },
            {
                "supplier": "Vendor G",
                "buyer": "Buyer H",
                "material": "Material 4",
                "confidence": 150,  # > 100 -> must be rejected
                "snippet": "Vendor G supplies Material 4 to Buyer H",
                "page": 1,
            },
        ]
    }
    mock_gemini_response = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_response
    mock_client.post.return_value = mock_response

    result = extract_relationships(
        text="Sample procurement text",
        api_key="mock_key",
        client=mock_client,
    )

    # Negative (-10) and >100 (150) must be rejected, so only 2 valid relationships remain
    assert len(result.relationships) == 2
    assert result.relationships[0].supplier == "Vendor A"
    assert result.relationships[0].confidence == pytest.approx(0.85)

    assert result.relationships[1].supplier == "Vendor C"
    assert result.relationships[1].confidence == pytest.approx(0.15)


# =============================================================================
# BluePeak Format & Share Percentage Regression Tests
# =============================================================================

def test_extract_bluepeak_procurement_format_regression():
    """
    Regression Test: Verifies fallback extraction on BluePeak_Procurement format:
    - Order-independent multi-line explicit labels (Supplier before Buyer)
    - Active present tense statement ('supplies')
    - Standard lead time: 12 days
    - Supply share format: 'Supply Share: 30%'
    """
    bluepeak_text = (
        "[DEMONSTRATION EVIDENCE]\r\n\r\n"
        "Supplier: BluePeak Chemicals Pvt Ltd\r\n\r\n"
        "Buyer: RubberCore Industries\r\n\r\n"
        "Material: Synthetic Rubber\r\n\r\n"
        "BluePeak Chemicals Pvt Ltd supplies Synthetic Rubber to RubberCore Industries.\r\n\r\n"
        "Lead Time: 12 days.\r\n\r\n"
        "Supply Share: 30%.\r\n\r\n"
        "This is fictional demonstration procurement data created for testing the TierLens AI "
        "document processing and supplier relationship review workflow."
    )

    result = extract_relationships(text=bluepeak_text, filename="BluePeak_Procurement.txt", api_key=None)
    assert isinstance(result, ExtractionResult)
    assert len(result.relationships) == 1

    rel = result.relationships[0]
    assert rel.supplier == "BluePeak Chemicals Pvt Ltd"
    assert rel.buyer == "RubberCore Industries"
    assert rel.material == "Synthetic Rubber"
    assert rel.lead_time_days == 12
    assert rel.share_pct == 30.0
    assert rel.confidence == 0.95
    assert rel.source_doc == "BluePeak_Procurement.txt"
    assert "BluePeak Chemicals Pvt Ltd supplies Synthetic Rubber to RubberCore Industries" in rel.snippet
    assert result.entities_found == 3


def test_extract_share_percentage_variations():
    """Verifies that both prefix and postfix share/allocation percentage formats extract correctly."""
    cases = [
        ("Supply Share: 30%.", 30.0),
        ("Share: 45.5%", 45.5),
        ("allocation: 60%", 60.0),
        ("Contract with 25% share of total volume.", 25.0),
        ("Guaranteed 75 % allocation to primary plant.", 75.0),
    ]
    for text_snippet, expected_share in cases:
        full_text = f"Supplier: Vendor Alpha\n\nBuyer: Buyer Beta\n\nMaterial: Raw Steel\n\n{text_snippet}"
        result = extract_relationships(text=full_text, filename="test.txt", api_key=None)
        assert len(result.relationships) == 1
        assert result.relationships[0].share_pct == pytest.approx(expected_share)


def test_extract_supplies_verb_without_explicit_labels():
    """Verifies Pattern 2 fallback matching with active verb 'supplies' without explicit key-value labels."""
    sentence_text = "Apex Materials Pvt Ltd supplies industrial rubber compound to TyreWorks Ltd monthly."
    result = extract_relationships(text=sentence_text, filename="sentence.txt", api_key=None)
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.supplier == "Apex Materials Pvt Ltd"
    assert rel.buyer == "TyreWorks Ltd"
    assert rel.material == "Processed Rubber"

