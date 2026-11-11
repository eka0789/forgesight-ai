from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MachineCreate(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    machine_type: str = Field(default="generic", max_length=64)
    location: str | None = Field(default=None, max_length=120)


class MachineUpdate(BaseModel):
    name: str | None = None
    machine_type: str | None = None
    location: str | None = None
    status: str | None = None
    is_active: bool | None = None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    machine_type: str
    location: str | None
    status: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReadingIn(BaseModel):
    """AI4I-style sensor reading. Temperatures in Kelvin, speed rpm, torque Nm, wear min."""
    air_temperature: float = Field(ge=200, le=500)
    process_temperature: float = Field(ge=200, le=500)
    rotational_speed: float = Field(ge=0, le=5000)
    torque: float = Field(ge=0, le=500)
    tool_wear: float = Field(ge=0, le=600)
    vibration: float | None = Field(default=None, ge=0, le=100)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    ts: datetime
    air_temperature: float
    process_temperature: float
    rotational_speed: float
    torque: float
    tool_wear: float
    vibration: float | None


class HealthIn(BaseModel):
    pass


class MachineHealthOut(BaseModel):
    machine_id: int
    machine_code: str
    status: str
    health_score: float
    failure_probability: float
    risk_level: str
    rul_hours: float | None = None
    predicted_modes: dict | None = None
    recommendations: list[str] | None = None
    model_version: str | None = None
    latest_reading: dict | None = None
    is_prediction_available: bool = False
    note: str | None = None
