"""Embedding provider abstraction.

Providers:
- LocalHashEmbeddingProvider: deterministic signed n-gram hashing, 384-d.
  *Training-free local fallback* — real vector math, weaker semantics.
  Clearly labeled wherever it is used.
- OpenAIEmbeddingProvider (text-embedding-3-small)
- HuggingFaceEmbeddingProvider (sentence-transformers MiniLM, 384-d)

Switching providers never touches business logic (settings only).
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import settings

TOKEN_RE = re.compile(r"[a-z0-9]+")


class BaseEmbeddingProvider(ABC):
    name: str = "base"
    dim: int = settings.embedding_dim

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class LocalHashEmbeddingProvider(BaseEmbeddingProvider):
    """Signed feature hashing over words + char 3-grams; L2-normalized."""

    name = "local_hash_384"

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim

    def _features(self, text: str) -> list[str]:
        low = text.lower()
        words = TOKEN_RE.findall(low)[:2000]
        chars = [low[i : i + 3] for i in range(max(0, len(low) - 2))][:4000]
        return words + chars

    def _index(self, feature: str) -> int:
        return int(hashlib.md5(feature.encode("utf-8")).hexdigest(), 16) % self.dim

    def embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for f in self._features(text):
            idx = self._index(f)
            sign = 1.0 if int(hashlib.md5(f.encode("utf-8")).hexdigest()[0], 16) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec)) or 1.0
        return [round(float(x / norm), 6) for x in vec]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    name = "openai"

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim
        self.model = "text-embedding-3-small"

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": self.model, "input": texts, "dimensions": self.dim},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [d["embedding"] for d in data]

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    name = "huggingface"

    def __init__(self):
        from sentence_transformers import SentenceTransformer  # guarded

        self.model = SentenceTransformer(settings.hf_embedding_model)
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [np.asarray(v, dtype=np.float32).tolist() for v in vectors]

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


_provider: BaseEmbeddingProvider | None = None


def get_embedding_provider() -> BaseEmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider
    kind = settings.embedding_provider
    if kind == "openai" and settings.openai_api_key:
        _provider = OpenAIEmbeddingProvider()
    elif kind == "huggingface":
        try:
            _provider = HuggingFaceEmbeddingProvider()
        except Exception:
            _provider = LocalHashEmbeddingProvider()
    else:
        _provider = LocalHashEmbeddingProvider()
    return _provider
