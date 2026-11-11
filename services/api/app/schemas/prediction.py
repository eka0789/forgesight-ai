from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    model_version: str
    failure_probability: float
    risk_level: str
    health_score: float
    rul_hours: float | None
    predicted_modes: dict | None
    recommendations: list | None
    input_snapshot: dict | None
    is_demo: bool | None
    created_at: datetime | None


class FailurePredictionOut(BaseModel):
    failure_probability: float
    risk_level: str
    predicted_modes: dict
    top_factors: list[dict]
    model_version: str
    model_metrics: dict | None = None
    recommendations: list[str]
    inference_ms: float


class RulOut(BaseModel):
    rul_hours: float
    model_version: str
    model_metrics: dict | None = None
    inference_ms: float


class MaintenanceRequestCreate(BaseModel):
    machine_id: int
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    priority: str = "medium"
    source: str = "manual"


class MaintenanceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    title: str
    description: str | None
    priority: str
    status: str
    source: str
    created_by: int | None
    approved_by: int | None
    created_at: datetime | None
    updated_at: datetime | None
