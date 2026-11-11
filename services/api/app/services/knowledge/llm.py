"""LLM provider abstraction: OpenAI, Gemini, and a clearly-labeled MockLLM.

The Mock provider produces *deterministic extractive answers built from the
retrieved context only* — it never invents facts and is marked
provider="mock-demo" in every response so demo mode is unmistakable.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.core.config import settings


class BaseLLM(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str, *, max_tokens: int = 900, temperature: float = 0.2) -> str: ...


class OpenAILLM(BaseLLM):
    name = "openai"

    def complete(self, system: str, user: str, *, max_tokens: int = 900, temperature: float = 0.2) -> str:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class GeminiLLM(BaseLLM):
    name = "gemini"

    def complete(self, system: str, user: str, *, max_tokens: int = 900, temperature: float = 0.2) -> str:
        import httpx

        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
            params={"key": settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


class MockLLM(BaseLLM):
    """Deterministic extractive 'generation' over provided context (DEMO MODE)."""

    name = "mock-demo"

    def complete(self, system: str, user: str, *, max_tokens: int = 900, temperature: float = 0.2) -> str:
        # The RAG layer passes context blocks headed by `[n] source=...`; the
        # mock extracts query-relevant sentences per block and re-emits them
        # with the matching [n] citation marker. No hallucination by design.
        # Two-pass: the QUESTION line is parsed first (it appears after the
        # context blocks), then context sentences are scored against it.
        header_re = re.compile(r"^\[(\d+)\]\s+source=")
        query = ""
        for line in user.splitlines():
            if line.startswith("QUESTION"):
                query = line.split(":", 1)[1].strip() if ":" in line else ""
                break
        q_tokens = set(re.findall(r"[a-z0-9]{3,}", query.lower()))

        current_citation = 0
        sentences: list[tuple[float, str]] = []
        for line in user.splitlines():
            m = header_re.match(line.strip())
            if m:
                current_citation = int(m.group(1))
                continue
            if line.startswith(("QUESTION", "INSTRUCTIONS")) or not line.strip() or current_citation == 0:
                continue
            for sent in re.split(r"(?<=[.!?])\s+", line.strip()):
                sent = sent.strip()
                if len(sent) < 30:
                    continue
                s_tokens = set(re.findall(r"[a-z0-9]{3,}", sent.lower()))
                overlap = len(q_tokens & s_tokens) / max(1, len(q_tokens))
                if overlap > 0:
                    sentences.append((overlap, f"{sent} [{current_citation}]"))

        sentences.sort(key=lambda x: -x[0])
        picked: list[str] = []
        seen: set[str] = set()
        for _, s in sentences[:6]:
            key = s[:60]
            if key not in seen:
                seen.add(key)
                picked.append(s)
        if not picked:
            return ("(Demo LLM) Retrieved context does not contain query-relevant sentences. "
                    "See the cited sources below for reference.")
        return "(Demo LLM — deterministic extractive answer from retrieved context)\n\n" + "\n\n".join(picked)


_llm: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm
    if _llm is not None:
        return _llm
    if settings.llm_provider == "openai" and settings.openai_api_key:
        _llm = OpenAILLM()
    elif settings.llm_provider == "gemini" and settings.gemini_api_key:
        _llm = GeminiLLM()
    else:
        _llm = MockLLM()
    return _llm
