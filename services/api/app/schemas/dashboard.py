from __future__ import annotations

from pydantic import BaseModel


class KpiOut(BaseModel):
    total_inspections: int
    total_defects: int
    defect_detection_rate: float
    avg_machine_health: float
    predicted_maintenance_events: int
    avg_inference_ms: float | None
    open_maintenance_requests: int


class TrendPoint(BaseModel):
    date: str
    inspections: int
    defects: int


class DefectDistItem(BaseModel):
    label: str
    count: int


class MachineStatusItem(BaseModel):
    status: str
    count: int


class ModelMetricItem(BaseModel):
    model_name: str
    task: str
    metrics: dict


class ActivityItem(BaseModel):
    ts: str
    kind: str
    title: str
    detail: str | None = None


class AiSystemHealth(BaseModel):
    llm_provider: str
    llm_mode: str
    embedding_provider: str
    artifacts_status: str
    status: str


class DashboardSummaryOut(BaseModel):
    kpis: KpiOut
    production_trend: list[TrendPoint]
    defect_distribution: list[DefectDistItem]
    machine_status: list[MachineStatusItem]
    model_metrics: list[ModelMetricItem]
    recent_activity: list[ActivityItem]
    ai_system_health: AiSystemHealth
    is_demo_data: bool
