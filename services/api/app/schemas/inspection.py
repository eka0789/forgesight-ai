from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DefectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    confidence: float
    bbox_x1: int | None = None
    bbox_y1: int | None = None
    bbox_x2: int | None = None
    bbox_y2: int | None = None
    severity: str | None = None
    method: str | None = None


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int | None
    kind: str
    filename: str
    status: str
    result: str | None
    defect_count: int
    avg_confidence: float | None
    method_used: str | None
    processing_ms: int | None
    model_version: str | None
    error: str | None
    is_demo: bool | None
    created_at: datetime | None
    completed_at: datetime | None


class InspectionDetailOut(InspectionOut):
    defects: list[DefectOut] = []
    images: list[dict] = []
    anomaly: dict | None = None
    ocr: dict | None = None
