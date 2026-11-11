from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    filename: str
    mime: str | None
    size_bytes: int | None
    page_count: int | None
    status: str
    error: str | None
    chunk_count: int
    is_demo: bool | None
    created_at: datetime | None


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=30)
    document_ids: list[int] | None = None
    metadata_filter: dict | None = None


class RetrievedChunkOut(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None


class SearchOut(BaseModel):
    query: str
    results: list[RetrievedChunkOut]
    retrieval_method: str


class CitationOut(BaseModel):
    index: int
    document_id: int
    document_title: str
    page_number: int | None = None
    chunk_index: int
    quote: str | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    top_k: int = Field(default=6, ge=1, le=20)


class ChatOut(BaseModel):
    conversation_id: int
    answer: str
    citations: list[CitationOut]
    llm_provider: str
    has_context: bool
    disclaimer: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    created_at: datetime | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    citations: list | None
    meta: dict | None
    created_at: datetime | None
