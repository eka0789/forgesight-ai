from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON as SAJSON
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AgentExecution(Base, TimestampMixin):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planner: Mapped[str] = mapped_column(String(16), default="rule_based", nullable=False)
    result: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tool_logs: Mapped[list["AgentToolLog"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentToolLog(Base):
    __tablename__ = "agent_tool_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id", ondelete="CASCADE"), index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ok", nullable=False)  # ok | error | awaiting_approval
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    execution = relationship("AgentExecution", back_populates="tool_logs")
