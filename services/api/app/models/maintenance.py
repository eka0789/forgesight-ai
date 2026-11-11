from __future__ import annotations

from sqlalchemy import JSON as SAJSON
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MaintenancePrediction(Base, TimestampMixin):
    __tablename__ = "maintenance_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False)
    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    rul_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_modes: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)   # {"TWF": 0.12, ...}
    recommendations: Mapped[list | None] = mapped_column(SAJSON, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    is_demo: Mapped[bool | None] = mapped_column(default=False, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class MaintenanceRequest(Base, TimestampMixin):
    __tablename__ = "maintenance_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(12), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    source: Mapped[str] = mapped_column(String(12), default="manual", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
