"""Text extraction for supported document types: PDF, TXT, DOCX, CSV.

Scanned-PDF OCR path is available only when the tesseract binary is present
(guarded — reported honestly otherwise).
"""
from __future__ import annotations

import io

SUPPORTED_MIME = {
    "pdf": ["application/pdf"],
    "txt": ["text/plain"],
    "docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "csv": ["text/csv", "application/vnd.ms-excel"],
}
SUPPORTED_EXT = {".pdf", ".txt", ".docx", ".csv", ".md"}


class UnsupportedDocument(ValueError):
    pass


def detect_kind(filename: str, mime: str | None) -> str:
    """Extension-first detection: a known-but-different MIME does NOT rescue an
    unknown extension (defense against disguised uploads like payload.sh with
    text/plain content-type)."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext in SUPPORTED_EXT:
        return ext.lstrip(".")
    if ext:  # explicit but unsupported extension → reject regardless of MIME
        raise UnsupportedDocument(
            f"Unsupported document extension '{ext}'. Supported: PDF, TXT, DOCX, CSV, MD."
        )
    for kind, mimes in SUPPORTED_MIME.items():
        if mime in mimes:
            return kind
    raise UnsupportedDocument(
        f"Unsupported document type ({filename or mime}). Supported: PDF, TXT, DOCX, CSV, MD."
    )


def _extract_pdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(f"[[page:{i + 1}]]\n{text}")
    joined = "\n\n".join(pages)
    if not joined.strip():
        raise UnsupportedDocument(
            "No extractable text layer (likely a scanned PDF). Install tesseract + pdf2image for OCR ingestion."
        )
    return joined, len(reader.pages)


def _extract_docx(data: bytes) -> tuple[str, int]:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paras), 1


def _extract_csv(data: bytes) -> tuple[str, int]:
    import pandas as pd

    df = pd.read_csv(io.BytesIO(data))
    # Render rows as readable text blocks for retrieval.
    lines = [", ".join(f"{c}={v}" for c, v in row.items() if pd.notna(v)) for _, row in df.iterrows()]
    header = "Columns: " + ", ".join(map(str, df.columns))
    return header + "\n\n" + "\n".join(lines[:5000]), 1


def _extract_txt(data: bytes) -> tuple[str, int]:
    return data.decode("utf-8", errors="replace"), 1


def extract_text(filename: str, data: bytes, mime: str | None = None) -> dict:
    kind = detect_kind(filename, mime)
    if kind == "pdf":
        text, pages = _extract_pdf(data)
    elif kind == "docx":
        text, pages = _extract_docx(data)
    elif kind == "csv":
        text, pages = _extract_csv(data)
    else:
        text, pages = _extract_txt(data)
    return {"text": text, "pages": pages, "kind": kind}
