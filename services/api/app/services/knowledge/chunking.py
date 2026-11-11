"""Document chunking: structure-aware recursive splitter with page tracking."""
from __future__ import annotations

import re

CHUNK_SIZE = 900
CHUNK_OVERLAP = 140
PAGE_MARKER = re.compile(r"\[\[page:(\d+)\]\]")


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        # Prefer breaking at sentence/paragraph boundary inside the window.
        if end < len(text):
            for sep in ("\n\n", ". ", "\n", " "):
                cut = text.rfind(sep, start + size // 2, end)
                if cut > start:
                    end = cut + len(sep)
                    break
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def chunk_document(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Splits into ~chunk_size pieces, tracking PDF page numbers via markers."""
    segments: list[tuple[str, int | None]] = []
    page = 1
    buf: list[str] = []
    for line in text.split("\n"):
        m = PAGE_MARKER.match(line.strip())
        if m:
            if buf:
                segments.append(("\n".join(buf), page))
                buf = []
            page = int(m.group(1))
            continue
        buf.append(line)
        if buf and sum(len(x) for x in buf) > chunk_size:
            segments.append(("\n".join(buf), page))
            buf = []
    if buf:
        segments.append(("\n".join(buf), page))

    chunks: list[dict] = []
    idx = 0
    for seg, seg_page in segments:
        if not seg.strip():
            continue
        if len(seg) <= chunk_size * 1.2:
            chunks.append({"index": idx, "content": seg, "page_number": seg_page, "tokens": len(seg) // 4})
            idx += 1
        else:
            for piece in _split_long(seg, chunk_size, overlap):
                if piece:
                    chunks.append({"index": idx, "content": piece, "page_number": seg_page, "tokens": len(piece) // 4})
                    idx += 1
    return chunks
