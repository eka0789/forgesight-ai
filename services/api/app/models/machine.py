from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Machine(Base, TimestampMixin):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    machine_type: Mapped[str] = mapped_column(String(64), default="generic", nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="healthy", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # NOTE: readings intentionally NOT a selectin relationship — sensor history
    # is large; always query SensorReading explicitly with time filters.


Index("ix_machines_org_code", Machine.org_id, Machine.code, unique=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    air_temperature: Mapped[float] = mapped_column(Float, nullable=False)      # K (AI4I schema)
    process_temperature: Mapped[float] = mapped_column(Float, nullable=False)  # K
    rotational_speed: Mapped[float] = mapped_column(Float, nullable=False)     # rpm
    torque: Mapped[float] = mapped_column(Float, nullable=False)               # Nm
    tool_wear: Mapped[float] = mapped_column(Float, nullable=False)            # min
    vibration: Mapped[float | None] = mapped_column(Float, nullable=True)      # mm/s (extra channel)
