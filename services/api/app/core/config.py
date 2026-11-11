"""Central application settings (pydantic-settings). No secrets are hardcoded."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent  # services/api/app
API_DIR = APP_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env", "../../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    app_name: str = "ForgeSight AI"
    env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Database
    database_url: str = "sqlite:///./forgesight.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_backend: str = "local"  # local | s3
    storage_dir: str = str(API_DIR / "storage")
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "forgesight"

    # Generative AI
    llm_provider: str = "mock"  # mock | openai | gemini
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Embeddings / RAG
    embedding_provider: str = "local"  # local | openai | huggingface
    embedding_dim: int = 384
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # MLflow (optional)
    mlflow_tracking_uri: str | None = None

    # Artifacts
    artifacts_dir: str | None = None

    # Demo
    seed_demo: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    rate_limit_login_per_minute: int = 10

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def resolved_artifacts_dir(self) -> Path:
        if self.artifacts_dir:
            return Path(self.artifacts_dir).resolve()
        # Walk up from app dir to find <repo>/ml/artifacts
        p = APP_DIR
        for _ in range(6):
            candidate = p / "ml" / "artifacts"
            if candidate.exists():
                return candidate
            p = p.parent
        return (API_DIR.parent.parent / "ml" / "artifacts").resolve()

    @property
    def llm_available(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
