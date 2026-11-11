from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    framework: str
    status: str
    artifact_path: str | None
    metrics: dict | None
    params: dict | None
    created_at: datetime | None


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task: str
    description: str | None
    versions: list[ModelVersionOut] = []


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    path: str | None
    rows: int | None
    description: str | None


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    params: dict | None
    metrics: dict | None
    artifact_uri: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    mlflow_run_id: str | None
