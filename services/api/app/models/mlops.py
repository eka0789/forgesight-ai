from __future__ import annotations

from sqlalchemy import JSON as SAJSON
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class MLModel(Base, TimestampMixin):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    task: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list["MLModelVersion"]] = relationship(
        back_populates="model", cascade="all, delete-orphan", lazy="selectin"
    )


class MLModelVersion(Base, TimestampMixin):
    __tablename__ = "ml_model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("ml_models.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="registered", nullable=False)
    metrics: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(String(64), nullable=True)

    model = relationship("MLModel", back_populates="versions")
    metrics_rows: Mapped[list["ModelMetric"]] = relationship(
        back_populates="model_version", cascade="all, delete-orphan", lazy="selectin"
    )


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("ml_model_versions.id", ondelete="CASCADE"), index=True, nullable=False)
    split: Mapped[str] = mapped_column(String(12), nullable=False)  # train | val | test
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    model_version = relationship("MLModelVersion", back_populates="metrics_rows")
