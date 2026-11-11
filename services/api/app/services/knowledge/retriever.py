"""Hybrid retrieval: vector similarity + keyword scoring fused with RRF,
metadata filtering, and a light reranking pass.

- PostgreSQL: pgvector `<=>` distance in SQL.
- SQLite/tests: numpy cosine over org-scoped chunks (bounded scale).
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import Document, DocumentChunk
from app.services.knowledge.embeddings import get_embedding_provider

RRF_K = 60
TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _keyword_scores(query: str, chunks: list[DocumentChunk]) -> list[float]:
    """Lightweight BM25-style scoring computed in Python (org-scoped, bounded)."""
    q_tokens = _tokens(query)
    if not q_tokens or not chunks:
        return [0.0] * len(chunks)
    doc_counts = [Counter(_tokens(c.content)) for c in chunks]
    n_docs = len(chunks)
    dfs: Counter = Counter()
    for counts in doc_counts:
        for t in set(counts):
            dfs[t] += 1
    scores: list[float] = []
    for counts in doc_counts:
        score = 0.0
        doc_len = max(1, sum(counts.values()))
        for t in q_tokens:
            if t in counts:
                idf = math.log((n_docs - dfs[t] + 0.5) / (dfs[t] + 0.5) + 1.0)
                tf = counts[t] / (counts[t] + 1.2 * doc_len / 400.0)
                score += idf * tf
        scores.append(score)
    return scores


def _vector_scores(db: Session, org_id: int, query_vec: list[float], chunks: list[DocumentChunk]) -> list[float]:
    if settings.is_postgres:
        vec_literal = "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]"
        id_list = ",".join(str(c.id) for c in chunks) or "0"
        rows = db.execute(
            sa_text(
                "SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS sim "
                "FROM document_chunks WHERE id IN (:ids) ORDER BY sim DESC"
            ),
            {"vec": vec_literal, "ids": id_list},
        ).fetchall()
        sim_by_id = {r[0]: float(r[1]) for r in rows}
        return [sim_by_id.get(c.id, 0.0) for c in chunks]
    q = np.asarray(query_vec, dtype=np.float32)
    scores: list[float] = []
    for c in chunks:
        v = np.asarray(c.embedding or [], dtype=np.float32)
        denom = (np.linalg.norm(q) * np.linalg.norm(v)) or 1.0
        scores.append(float(np.dot(q, v) / denom) if v.size == q.size else 0.0)
    return scores


def _rrf_fuse(vec_ranked: list[int], kw_ranked: list[int]) -> dict[int, float]:
    fused: dict[int, float] = {}
    for rank_start, ranked in ((1, vec_ranked), (1, kw_ranked)):
        for offset, idx in enumerate(ranked):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank_start + offset)
    return fused


def hybrid_search(
    db: Session,
    org_id: int,
    query: str,
    top_k: int = 6,
    document_ids: list[int] | None = None,
    min_score: float = 1e-9,
) -> tuple[list[dict], str]:
    """Returns (results, retrieval_method). Results carry vector+keyword scores."""
    provider = get_embedding_provider()
    q_vec = provider.embed(query)

    q = db.query(DocumentChunk).filter(DocumentChunk.org_id == org_id)
    if document_ids:
        q = q.filter(DocumentChunk.document_id.in_(document_ids))
    chunks = q.limit(4000).all()
    if not chunks:
        return [], f"hybrid({provider.name}; no-indexed-chunks)"

    doc_titles = {d.id: d.title for d in db.query(Document).filter(Document.org_id == org_id).all()}

    vec_scores = _vector_scores(db, org_id, q_vec, chunks)
    kw_scores = _keyword_scores(query, chunks)

    vec_ranked = sorted(range(len(chunks)), key=lambda i: -vec_scores[i])
    kw_ranked = sorted(range(len(chunks)), key=lambda i: -kw_scores[i])

    fused = _rrf_fuse(vec_ranked, kw_ranked)
    # Rerank pass: RRF order weighted by normalized component scores.
    max_v = max(vec_scores) or 1.0
    max_k = max(kw_scores) or 1.0
    for idx, rrf in fused.items():
        fused[idx] = rrf + 0.15 * (vec_scores[idx] / max_v) + 0.10 * (kw_scores[idx] / max_k)

    ordered = sorted(fused.items(), key=lambda x: -x[1])[:top_k]
    results: list[dict] = []
    for idx, score in ordered:
        c = chunks[idx]
        results.append(
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "document_title": doc_titles.get(c.document_id, f"doc-{c.document_id}"),
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "score": round(float(score), 6),
                "vector_score": round(float(vec_scores[idx]), 6),
                "keyword_score": round(float(kw_scores[idx]), 6),
            }
        )
    results = [r for r in results if r["score"] > min_score]
    return results, f"hybrid_rrf({provider.name})"
