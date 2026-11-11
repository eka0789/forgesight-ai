from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON as SAJSON
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MLDataset(Base):
    __tablename__ = "ml_datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)  # tabular | image | text
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class MLExperiment(Base):
    __tablename__ = "ml_experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)  # classification | regression | clustering | cv | rl
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("ml_datasets.id", ondelete="SET NULL"), nullable=True)
    params: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="completed", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    dataset = relationship("MLDataset")
