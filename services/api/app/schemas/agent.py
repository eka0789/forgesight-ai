from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class ToolLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tool_name: str
    args: dict | None
    result: dict | None
    status: str
    duration_ms: int | None


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int | None
    input: str
    status: str
    iterations: int
    planner: str
    result: dict | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ExecutionDetailOut(ExecutionOut):
    tool_logs: list[ToolLogOut] = []


class ApprovalOut(BaseModel):
    execution_id: int
    status: str
    tool: str | None
    args: dict | None
    message: str
