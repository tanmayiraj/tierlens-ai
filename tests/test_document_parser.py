"""
Unit and integration tests for Document Parsing Service (Milestone 4: TASK-022).
Tests cover PDF, TXT, CSV parsing, chunking, page counting, encoding fallbacks,
and error conditions (empty, corrupt, encrypted, unsupported).
Uses isolated temporary files and does not access or modify the database.
"""

import io
import pytest
from pathlib import Path
from pypdf import PdfReader, PdfWriter

from backend.services.document_parser import (
    parse_document,
    chunk_document_pages,
    ParsedDocument,
    ParsedChunk,
    DocumentParseError,
    EmptyDocumentError,
    CorruptDocumentError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)


def _generate_valid_two_page_pdf_bytes(p1_text: str, p2_text: str) -> bytes:
    """Generates valid 2-page PDF binary data with extractable text."""
    p1_escaped = p1_text.replace("(", r"\(").replace(")", r"\)")
    p2_escaped = p2_text.replace("(", r"\(").replace(")", r"\)")
    raw_pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >> endobj
4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >> endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
6 0 obj << /Length {len(p1_escaped) + 40} >> stream
BT
/F1 12 Tf
72 712 Td
({p1_escaped}) Tj
ET
endstream
endobj
7 0 obj << /Length {len(p2_escaped) + 40} >> stream
BT
/F1 12 Tf
72 712 Td
({p2_escaped}) Tj
ET
endstream
endobj
xref
0 8
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000125 00000 n 
0000000244 00000 n 
0000000363 00000 n 
0000000438 00000 n 
0000000542 00000 n 
trailer << /Size 8 /Root 1 0 R >>
startxref
646
%%EOF""".encode("latin-1")

    reader = PdfReader(io.BytesIO(raw_pdf))
    writer = PdfWriter()
    writer.append(reader)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# =============================================================================
# PDF Parsing Tests
# =============================================================================

def test_parse_valid_two_page_pdf(tmp_path):
    """Verifies that a valid two-page PDF extracts text page-by-page with page_count=2."""
    p1 = "Purchase Order PO_1042: GreenLatex supplies 40 MT natural latex to RubberCore."
    p2 = "Terms: Net 30 days. Delivery to Chennai storage hub."
    pdf_bytes = _generate_valid_two_page_pdf_bytes(p1, p2)

    pdf_file = tmp_path / "valid_order.pdf"
    pdf_file.write_bytes(pdf_bytes)

    res = parse_document(pdf_file)
    assert isinstance(res, ParsedDocument)
    assert res.page_count == 2
    assert p1 in res.raw_text
    assert p2 in res.raw_text

    # Chunks verification
    assert len(res.chunks) >= 2
    p1_chunks = [c for c in res.chunks if c.page == 1]
    p2_chunks = [c for c in res.chunks if c.page == 2]
    assert len(p1_chunks) >= 1
    assert len(p2_chunks) >= 1
    assert p1 in p1_chunks[0].snippet
    assert p2 in p2_chunks[0].snippet


def test_parse_corrupt_pdf(tmp_path):
    """Verifies that a corrupt or damaged PDF raises CorruptDocumentError."""
    corrupt_file = tmp_path / "broken.pdf"
    corrupt_file.write_bytes(b"%PDF-1.4\nCorrupted content without catalog or xref table...")

    with pytest.raises(CorruptDocumentError) as exc_info:
        parse_document(corrupt_file)
    assert "Corrupt or invalid PDF file" in str(exc_info.value)


def test_parse_encrypted_pdf(tmp_path):
    """Verifies that an encrypted / password-protected PDF raises EncryptedDocumentError."""
    pdf_bytes = _generate_valid_two_page_pdf_bytes("Secret Page 1", "Secret Page 2")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt("mypassword")

    enc_buf = io.BytesIO()
    writer.write(enc_buf)

    enc_file = tmp_path / "protected.pdf"
    enc_file.write_bytes(enc_buf.getvalue())

    with pytest.raises(EncryptedDocumentError) as exc_info:
        parse_document(enc_file)
    assert "encrypted or password-protected" in str(exc_info.value)


# =============================================================================
# TXT Parsing Tests
# =============================================================================

def test_parse_valid_txt(tmp_path):
    """Verifies parsing a standard UTF-8 text file."""
    txt_content = (
        "Supply Agreement: RubberCore Industries to supply processed rubber compound to TyreWorks Ltd.\n\n"
        "Contract Duration: 12 months with automatic renewal.\n"
        "Material Specifications: Grade A vulcanized compound."
    )
    txt_file = tmp_path / "contract.txt"
    txt_file.write_text(txt_content, encoding="utf-8")

    res = parse_document(txt_file)
    assert res.page_count == 1
    assert "RubberCore Industries" in res.raw_text
    assert len(res.chunks) >= 1
    for chunk in res.chunks:
        assert chunk.page == 1
        assert len(chunk.snippet.strip()) > 0


def test_parse_non_utf8_txt(tmp_path):
    """Verifies safe fallback reading for non-UTF-8 encodings (Latin-1)."""
    latin1_text = "Fournisseur: Société de Caoutchouc; Matériau: Latex Naturel; Quantité: 50 MT."
    txt_file = tmp_path / "french_supplier.txt"
    txt_file.write_bytes(latin1_text.encode("latin-1"))

    res = parse_document(txt_file)
    assert res.page_count == 1
    assert "Société de Caoutchouc" in res.raw_text
    assert len(res.chunks) >= 1


def test_parse_utf16_le_txt_with_bom(tmp_path):
    """Verifies UTF-16 Little-Endian text files with BOM prefix are correctly decoded."""
    content = "Procurement Record: GreenLatex supplies 40 MT Natural Latex."
    txt_bytes = b"\xff\xfe" + content.encode("utf-16-le")
    txt_file = tmp_path / "utf16_le.txt"
    txt_file.write_bytes(txt_bytes)

    res = parse_document(txt_file)
    assert res.page_count == 1
    assert "GreenLatex supplies 40 MT Natural Latex." in res.raw_text
    assert "\x00" not in res.raw_text  # Must not contain null bytes from failed latin-1 fallback
    assert len(res.chunks) >= 1


def test_parse_utf16_be_txt_with_bom(tmp_path):
    """Verifies UTF-16 Big-Endian text files with BOM prefix are correctly decoded."""
    content = "Procurement Record: PetroChem Asia supplies 25 MT Carbon Black."
    txt_bytes = b"\xfe\xff" + content.encode("utf-16-be")
    txt_file = tmp_path / "utf16_be.txt"
    txt_file.write_bytes(txt_bytes)

    res = parse_document(txt_file)
    assert res.page_count == 1
    assert "PetroChem Asia supplies 25 MT Carbon Black." in res.raw_text
    assert "\x00" not in res.raw_text
    assert len(res.chunks) >= 1


def test_parse_cp1252_txt_with_euro(tmp_path):
    """Verifies CP1252 encoded files containing the Euro symbol (€) are decoded accurately."""
    content = "Supplier invoice total: 18,500 € for synthetic rubber batches."
    txt_bytes = content.encode("cp1252")
    txt_file = tmp_path / "cp1252_euro.txt"
    txt_file.write_bytes(txt_bytes)

    res = parse_document(txt_file)
    assert res.page_count == 1
    assert "18,500 €" in res.raw_text
    assert len(res.chunks) >= 1


# =============================================================================
# CSV Parsing Tests
# =============================================================================

def test_parse_valid_csv(tmp_path):
    """Verifies parsing CSV file into structured readable text preserving column relations."""
    csv_content = (
        "supplier,material,lead_time_days,share_pct\n"
        "Alpha Corp,Natural Latex,21,70\n"
        "Beta Ltd,Synthetic Rubber,14,30\n"
    )
    csv_file = tmp_path / "suppliers.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    res = parse_document(csv_file)
    assert res.page_count == 1
    assert "Record 1:" in res.raw_text
    assert "supplier: Alpha Corp" in res.raw_text
    assert "material: Natural Latex" in res.raw_text
    assert "Record 2:" in res.raw_text
    assert "supplier: Beta Ltd" in res.raw_text

    # Chunks must preserve whole records
    assert len(res.chunks) >= 1
    for chunk in res.chunks:
        assert chunk.page == 1
        assert len(chunk.snippet.strip()) > 0


# =============================================================================
# Empty Files & Validation Error Tests
# =============================================================================

def test_parse_empty_files_rejected(tmp_path):
    """Verifies that 0-byte or whitespace-only files raise EmptyDocumentError."""
    # 0-byte PDF
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")
    with pytest.raises(EmptyDocumentError):
        parse_document(empty_pdf)

    # 0-byte TXT
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_bytes(b"")
    with pytest.raises(EmptyDocumentError):
        parse_document(empty_txt)

    # Whitespace-only TXT
    space_txt = tmp_path / "whitespace.txt"
    space_txt.write_text("   \n\n\t  \n  ", encoding="utf-8")
    with pytest.raises(EmptyDocumentError):
        parse_document(space_txt)

    # 0-byte CSV
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_bytes(b"")
    with pytest.raises(EmptyDocumentError):
        parse_document(empty_csv)


def test_parse_unsupported_format(tmp_path):
    """Verifies that unsupported file extensions raise UnsupportedFormatError."""
    doc_file = tmp_path / "document.docx"
    doc_file.write_bytes(b"Mock docx binary data")

    with pytest.raises(UnsupportedFormatError) as exc_info:
        parse_document(doc_file)
    assert "Unsupported file format '.docx'" in str(exc_info.value)


def test_parse_non_existent_file():
    """Verifies that non-existent file path raises FileNotFoundError."""
    missing = Path("non_existent_folder_xyz/file.pdf")
    with pytest.raises(FileNotFoundError):
        parse_document(missing)


# =============================================================================
# Chunk Ordering and Cleanliness Tests
# =============================================================================

def test_chunk_ordering_and_page_numbering(tmp_path):
    """Verifies sequential zero-based chunk_index and accurate page numbers."""
    p1 = "Paragraph 1 on Page 1.\n\nParagraph 2 on Page 1."
    p2 = "Paragraph 1 on Page 2.\n\nParagraph 2 on Page 2."
    pdf_bytes = _generate_valid_two_page_pdf_bytes(p1, p2)

    pdf_file = tmp_path / "ordered.pdf"
    pdf_file.write_bytes(pdf_bytes)

    res = parse_document(pdf_file)
    assert len(res.chunks) >= 2

    # Check indices are strictly 0, 1, 2, ...
    for expected_idx, chunk in enumerate(res.chunks):
        assert chunk.chunk_index == expected_idx
        assert chunk.page in (1, 2)
        assert len(chunk.snippet.strip()) > 0


def test_no_empty_chunks():
    """Verifies chunk_document_pages produces no empty or whitespace-only snippets."""
    pages = [
        (1, "\n\n   \n\nMeaningful text here.\n\n   \n\nAnother line."),
        (2, "\n   \n\nSecond page text."),
    ]
    chunks = chunk_document_pages(pages, is_csv=False)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.snippet.strip() != ""
        assert isinstance(c.chunk_index, int)
        assert c.page in (1, 2)
