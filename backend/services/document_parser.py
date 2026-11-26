"""
Document parsing and chunking service for TierLens AI (Milestone 4: TASK-022).
Extracts raw text, computes page counts, and produces structured chunks from
PDF, TXT, and CSV procurement documents.
Conforms to ARCHITECTURE.md Section 3.1 and DATABASE_SCHEMA.md Section 3.6.
"""

import io
import re
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pypdf
from pypdf.errors import PdfReadError


# =============================================================================
# Custom Parsing Exceptions
# =============================================================================

class DocumentParseError(Exception):
    """Base exception for all document parsing failures."""
    pass


class EmptyDocumentError(DocumentParseError):
    """Raised when a document is zero bytes or yields no extractable text."""
    pass


class CorruptDocumentError(DocumentParseError):
    """Raised when a document cannot be parsed due to corrupt or invalid data."""
    pass


class EncryptedDocumentError(DocumentParseError):
    """Raised when a PDF document is encrypted or password-protected."""
    pass


class UnsupportedFormatError(DocumentParseError):
    """Raised when a document format is not supported."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ParsedChunk:
    """
    Represents a discrete text chunk for AI extraction and evidence linkage.
    Conforms to DATABASE_SCHEMA.md Section 3.6 (evidence table columns: page, chunk_index, snippet).
    """
    page: Optional[int]
    chunk_index: int
    snippet: str


@dataclass
class ParsedDocument:
    """
    Represents the complete parsed result of a procurement document.
    """
    raw_text: str
    page_count: int
    chunks: List[ParsedChunk]


# =============================================================================
# Internal Parsers
# =============================================================================

def _parse_pdf(path: Path) -> Tuple[str, int, List[Tuple[int, str]]]:
    """
    Parses a PDF document page by page using pypdf.
    Returns:
        (raw_text, page_count, list of (1-based page number, extracted text))
    """
    if path.stat().st_size == 0:
        raise EmptyDocumentError(f"PDF file '{path.name}' is empty (0 bytes).")

    try:
        reader = pypdf.PdfReader(str(path))
    except (PdfReadError, Exception) as exc:
        raise CorruptDocumentError(f"Corrupt or invalid PDF file '{path.name}': {exc}") from exc

    if reader.is_encrypted:
        raise EncryptedDocumentError(f"PDF file '{path.name}' is encrypted or password-protected.")

    page_count = len(reader.pages)
    if page_count == 0:
        raise EmptyDocumentError(f"PDF file '{path.name}' contains no pages.")

    pages_text: List[Tuple[int, str]] = []
    full_text_parts: List[str] = []

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            raise CorruptDocumentError(
                f"Failed to extract text from page {page_num} of '{path.name}': {exc}"
            ) from exc

        clean_text = extracted.strip()
        if clean_text:
            pages_text.append((page_num, clean_text))
            full_text_parts.append(clean_text)

    if not pages_text or not any(t.strip() for _, t in pages_text):
        raise EmptyDocumentError(f"PDF file '{path.name}' contains no extractable text.")

    raw_text = "\n\n".join(full_text_parts)
    return raw_text, page_count, pages_text


def _parse_txt(path: Path) -> Tuple[str, int, List[Tuple[int, str]]]:
    """
    Parses a plain text document. Reads UTF-8 first with safe encoding fallbacks.
    Returns:
        (raw_text, page_count=1, [(1, text)])
    """
    if path.stat().st_size == 0:
        raise EmptyDocumentError(f"Text file '{path.name}' is empty (0 bytes).")

    raw_bytes = path.read_bytes()
    if not raw_bytes.strip():
        raise EmptyDocumentError(f"Text file '{path.name}' contains only whitespace.")

    # 1. Detect UTF-16 BOM prefixes explicitly first
    content: Optional[str] = None
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            content = raw_bytes.decode("utf-16")
        except UnicodeDecodeError:
            content = None

    # 2. For non-BOM files or if UTF-16 decode fails, try in order: utf-8, utf-8-sig, cp1252, latin-1
    if content is None:
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        for enc in encodings:
            try:
                content = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

    if content is None:
        content = raw_bytes.decode("utf-8", errors="replace")

    clean_content = content.strip()
    if not clean_content:
        raise EmptyDocumentError(f"Text file '{path.name}' contains no readable text.")

    return clean_content, 1, [(1, clean_content)]


def _parse_csv(path: Path) -> Tuple[str, int, List[Tuple[int, str]]]:
    """
    Parses a CSV document using standard library csv.
    Formats headers and row values into structured key-value lines to preserve
    semantic relationships for downstream entity extraction.
    Returns:
        (raw_text, page_count=1, [(1, formatted_text)])
    """
    if path.stat().st_size == 0:
        raise EmptyDocumentError(f"CSV file '{path.name}' is empty (0 bytes).")

    raw_bytes = path.read_bytes()
    if not raw_bytes.strip():
        raise EmptyDocumentError(f"CSV file '{path.name}' contains only whitespace.")

    # 1. Detect UTF-16 BOM prefixes explicitly first
    decoded: Optional[str] = None
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            decoded = raw_bytes.decode("utf-16")
        except UnicodeDecodeError:
            decoded = None

    # 2. For non-BOM files or if UTF-16 decode fails, try in order: utf-8, utf-8-sig, cp1252, latin-1
    if decoded is None:
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        for enc in encodings:
            try:
                decoded = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

    if decoded is None:
        decoded = raw_bytes.decode("utf-8", errors="replace")

    try:
        reader = list(csv.reader(io.StringIO(decoded)))
    except Exception as exc:
        raise CorruptDocumentError(f"Failed to parse CSV file '{path.name}': {exc}") from exc

    # Filter out completely empty rows
    non_empty_rows = [
        [cell.strip() for cell in row]
        for row in reader
        if any(cell.strip() for cell in row)
    ]
    if not non_empty_rows:
        raise EmptyDocumentError(f"CSV file '{path.name}' contains no readable data rows.")

    header = non_empty_rows[0]
    data_rows = non_empty_rows[1:]

    formatted_lines: List[str] = []
    if data_rows:
        for row_idx, row in enumerate(data_rows, start=1):
            row_items = []
            for col_idx, cell in enumerate(row):
                if cell:
                    col_name = (
                        header[col_idx]
                        if col_idx < len(header) and header[col_idx]
                        else f"Column_{col_idx + 1}"
                    )
                    row_items.append(f"{col_name}: {cell}")
            if row_items:
                formatted_lines.append(f"Record {row_idx}: " + ", ".join(row_items))
    else:
        # Header-only CSV
        formatted_lines.append("Header: " + ", ".join(header))

    raw_text = "\n".join(formatted_lines)
    return raw_text, 1, [(1, raw_text)]


# =============================================================================
# Chunking Helper
# =============================================================================

def chunk_document_pages(
    pages_text: List[Tuple[int, str]],
    is_csv: bool = False,
    max_chunk_chars: int = 1000,
) -> List[ParsedChunk]:
    """
    Segments extracted text into discrete non-empty chunks.
    Maintains 1-based page numbers and sequential zero-based chunk_index values.
    Preserves whole records for CSV and whole paragraphs/sentences for text/PDF.
    """
    chunks: List[ParsedChunk] = []
    current_chunk_idx = 0

    for page_num, text in pages_text:
        if is_csv:
            # Group complete CSV lines without breaking individual records
            records = [line.strip() for line in text.split("\n") if line.strip()]
            buffer: List[str] = []
            current_len = 0

            for rec in records:
                if current_len + len(rec) + 1 > max_chunk_chars and buffer:
                    snippet = "\n".join(buffer).strip()
                    if snippet:
                        chunks.append(
                            ParsedChunk(
                                page=page_num,
                                chunk_index=current_chunk_idx,
                                snippet=snippet,
                            )
                        )
                        current_chunk_idx += 1
                    buffer = [rec]
                    current_len = len(rec)
                else:
                    buffer.append(rec)
                    current_len += len(rec) + 1

            if buffer:
                snippet = "\n".join(buffer).strip()
                if snippet:
                    chunks.append(
                        ParsedChunk(
                            page=page_num,
                            chunk_index=current_chunk_idx,
                            snippet=snippet,
                        )
                    )
                    current_chunk_idx += 1

        else:
            # For PDF and TXT, split on paragraph breaks (\n\n or \n)
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

            buffer: List[str] = []
            current_len = 0

            for para in paragraphs:
                # If paragraph itself exceeds max_chunk_chars, split on sentence boundaries
                if len(para) > max_chunk_chars:
                    if buffer:
                        snippet = "\n\n".join(buffer).strip()
                        if snippet:
                            chunks.append(
                                ParsedChunk(
                                    page=page_num,
                                    chunk_index=current_chunk_idx,
                                    snippet=snippet,
                                )
                            )
                            current_chunk_idx += 1
                        buffer = []
                        current_len = 0

                    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
                    sent_buffer: List[str] = []
                    sent_len = 0
                    for s in sentences:
                        if sent_len + len(s) + 1 > max_chunk_chars and sent_buffer:
                            snippet = " ".join(sent_buffer).strip()
                            if snippet:
                                chunks.append(
                                    ParsedChunk(
                                        page=page_num,
                                        chunk_index=current_chunk_idx,
                                        snippet=snippet,
                                    )
                                )
                                current_chunk_idx += 1
                            sent_buffer = [s]
                            sent_len = len(s)
                        else:
                            sent_buffer.append(s)
                            sent_len += len(s) + 1
                    if sent_buffer:
                        snippet = " ".join(sent_buffer).strip()
                        if snippet:
                            chunks.append(
                                ParsedChunk(
                                    page=page_num,
                                    chunk_index=current_chunk_idx,
                                    snippet=snippet,
                                )
                            )
                            current_chunk_idx += 1
                elif current_len + len(para) + 2 > max_chunk_chars and buffer:
                    snippet = "\n\n".join(buffer).strip()
                    if snippet:
                        chunks.append(
                            ParsedChunk(
                                page=page_num,
                                chunk_index=current_chunk_idx,
                                snippet=snippet,
                            )
                        )
                        current_chunk_idx += 1
                    buffer = [para]
                    current_len = len(para)
                else:
                    buffer.append(para)
                    current_len += len(para) + 2

            if buffer:
                snippet = "\n\n".join(buffer).strip()
                if snippet:
                    chunks.append(
                        ParsedChunk(
                            page=page_num,
                            chunk_index=current_chunk_idx,
                            snippet=snippet,
                        )
                    )
                    current_chunk_idx += 1

    return chunks


# =============================================================================
# Public API
# =============================================================================

def parse_document(file_path: Union[str, Path], doc_type: Optional[str] = None) -> ParsedDocument:
    """
    Parses a procurement document (PDF, TXT, or CSV) from disk.
    Extracts raw text, counts total pages, and segments content into structured chunks.

    Args:
        file_path: Filesystem path to the document.
        doc_type: Optional explicit document type (e.g. purchase_order, contract, etc.).

    Returns:
        ParsedDocument containing raw_text, page_count, and chunks.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        EmptyDocumentError: If the file is 0 bytes or contains no extractable text.
        CorruptDocumentError: If the file cannot be parsed or read.
        EncryptedDocumentError: If the PDF is password-protected.
        UnsupportedFormatError: If the file extension is not supported (.pdf, .txt, .csv).
    """
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Document file not found: '{file_path}'")

    ext = path.suffix.lower()

    if ext == ".pdf":
        raw_text, page_count, pages_text = _parse_pdf(path)
        chunks = chunk_document_pages(pages_text, is_csv=False)
    elif ext == ".txt":
        raw_text, page_count, pages_text = _parse_txt(path)
        chunks = chunk_document_pages(pages_text, is_csv=False)
    elif ext == ".csv":
        raw_text, page_count, pages_text = _parse_csv(path)
        chunks = chunk_document_pages(pages_text, is_csv=True)
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}' for file '{path.name}'. Allowed formats: .pdf, .txt, .csv"
        )

    return ParsedDocument(
        raw_text=raw_text,
        page_count=page_count,
        chunks=chunks,
    )
