from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class HealthStatus(BaseModel):
    status: str
    database: str
    redis: str
    storage: str
    artifacts: str
    llm_provider: str
    embedding_provider: str
    version: str
