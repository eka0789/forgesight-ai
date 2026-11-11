from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.core.enums import MachineStatus
from app.core.metrics import MODEL_INFERENCE_LATENCY
from app.models.machine import Machine, SensorReading
from app.models.maintenance import MaintenancePrediction
from app.schemas.common import Page
from app.schemas.machine import (
    MachineCreate,
    MachineHealthOut,
    MachineOut,
    MachineUpdate,
    ReadingIn,
    ReadingOut,
)
from app.schemas.prediction import PredictionOut
from app.services.audit import audit_log
from app.services.pdm import inference as pdm

router = APIRouter(prefix="/machines", tags=["machines"])


def _org_machine(db, org_id: int, machine_id: int) -> Machine:
    m = db.query(Machine).filter(Machine.id == machine_id, Machine.org_id == org_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    return m


@router.get("", response_model=Page[MachineOut])
def list_machines(current: CurrentUserDep, db: DbDep, page: PageParams):
    q = db.query(Machine).filter(Machine.org_id == current.org_id, Machine.is_active.is_(True))
    total = q.count()
    items = q.order_by(Machine.code).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[MachineOut](
        items=[MachineOut.model_validate(m) for m in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.post("", response_model=MachineOut, status_code=201)
def create_machine(payload: MachineCreate, request: Request, current: CurrentUserDep, db: DbDep):
    require("manage_machines")(current)
    if db.query(Machine).filter(Machine.org_id == current.org_id, Machine.code == payload.code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Machine code already exists")
    m = Machine(org_id=current.org_id, **payload.model_dump())
    db.add(m)
    audit_log(db, org_id=current.org_id, user_id=current.id, action="machine_create",
              resource="machine", resource_id=m.id, ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(m)
    return MachineOut.model_validate(m)


@router.get("/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, current: CurrentUserDep, db: DbDep):
    return MachineOut.model_validate(_org_machine(db, current.org_id, machine_id))


@router.patch("/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: int, payload: MachineUpdate, current: CurrentUserDep, db: DbDep):
    require("manage_machines")(current)
    m = _org_machine(db, current.org_id, machine_id)
    data = payload.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in [s.value for s in MachineStatus]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status")
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return MachineOut.model_validate(m)


@router.delete("/{machine_id}", status_code=204)
def deactivate_machine(machine_id: int, current: CurrentUserDep, db: DbDep):
    """Soft deletion: machines are deactivated, never hard-deleted (audit history)."""
    require("manage_machines")(current)
    m = _org_machine(db, current.org_id, machine_id)
    m.is_active = False
    m.status = MachineStatus.OFFLINE.value
    db.commit()
    return None


@router.post("/{machine_id}/readings", response_model=ReadingOut, status_code=201)
def ingest_reading(machine_id: int, payload: ReadingIn, current: CurrentUserDep, db: DbDep):
    require("manage_machines")(current)
    m = _org_machine(db, current.org_id, machine_id)
    reading = SensorReading(machine_id=m.id, ts=datetime.now(timezone.utc), **payload.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return ReadingOut.model_validate(reading)


@router.get("/{machine_id}/readings", response_model=Page[ReadingOut])
def list_readings(machine_id: int, current: CurrentUserDep, db: DbDep, page: PageParams, days: int = 7):
    _org_machine(db, current.org_id, machine_id)
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 365))
    q = db.query(SensorReading).filter(
        SensorReading.machine_id == machine_id, SensorReading.ts >= since
    )
    total = q.count()
    items = q.order_by(SensorReading.ts.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[ReadingOut](
        items=[ReadingOut.model_validate(r) for r in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.get("/{machine_id}/health", response_model=MachineHealthOut)
def machine_health(machine_id: int, current: CurrentUserDep, db: DbDep):
    m = _org_machine(db, current.org_id, machine_id)
    latest = (
        db.query(SensorReading)
        .filter(SensorReading.machine_id == m.id)
        .order_by(SensorReading.ts.desc())
        .first()
    )
    if not latest:
        return MachineHealthOut(
            machine_id=m.id, machine_code=m.code, status=m.status, health_score=0.0,
            failure_probability=0.0, risk_level="unknown",
            note="No sensor readings available yet.",
        )
    payload = {
        "air_temperature": latest.air_temperature, "process_temperature": latest.process_temperature,
        "rotational_speed": latest.rotational_speed, "torque": latest.torque,
        "tool_wear": latest.tool_wear, "vibration": latest.vibration,
    }
    import time as _time

    t0 = _time.perf_counter()
    result = pdm.predict_failure(payload)
    rul = None
    try:
        rul = pdm.predict_rul(payload)["rul_hours"]
    except Exception:
        rul = None
    MODEL_INFERENCE_LATENCY.labels(model="failure_classifier").observe(_time.perf_counter() - t0)
    return MachineHealthOut(
        machine_id=m.id, machine_code=m.code, status=m.status,
        health_score=pdm.health_score(result, rul),
        failure_probability=result["failure_probability"], risk_level=result["risk_level"],
        rul_hours=rul, predicted_modes=result["predicted_modes"],
        recommendations=result["recommendations"], model_version=result["model_version"],
        latest_reading={"ts": str(latest.ts), **payload},
        is_prediction_available=result["model_version"] != "rules-only-fallback",
        note=None if result["model_version"] != "rules-only-fallback"
        else "Trained model artifact missing — rule-based fallback. Run ml/training scripts.",
    )


@router.get("/{machine_id}/predictions", response_model=Page[PredictionOut])
def machine_predictions(machine_id: int, current: CurrentUserDep, db: DbDep, page: PageParams):
    _org_machine(db, current.org_id, machine_id)
    q = db.query(MaintenancePrediction).filter(
        MaintenancePrediction.machine_id == machine_id,
        MaintenancePrediction.org_id == current.org_id,
    )
    total = q.count()
    items = q.order_by(MaintenancePrediction.created_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[PredictionOut](
        items=[PredictionOut.model_validate(p) for p in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )
