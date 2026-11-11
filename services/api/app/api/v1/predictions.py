from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.core.enums import MaintenanceRequestStatus
from app.core.metrics import PREDICTIONS_TOTAL
from app.models.machine import Machine, SensorReading
from app.models.maintenance import MaintenancePrediction, MaintenanceRequest
from app.schemas.common import Page
from app.schemas.machine import ReadingIn
from app.schemas.prediction import (
    FailurePredictionOut,
    MaintenanceRequestCreate,
    MaintenanceRequestOut,
    PredictionOut,
    RulOut,
)
from app.services.audit import audit_log
from app.services.pdm import inference as pdm

router = APIRouter(prefix="/predictions", tags=["predictions"])


class FailureIn(BaseModel):
    machine_id: int | None = None
    reading: ReadingIn | None = None


class RulIn(BaseModel):
    machine_id: int | None = None
    reading: ReadingIn | None = None
    cycles_elapsed: float | None = None


def _resolve_reading(db, org_id: int, body: FailureIn | RulIn) -> tuple[dict, Machine | None]:
    if body.reading is not None:
        return body.reading.model_dump(), None
    if body.machine_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide machine_id or reading")
    m = db.query(Machine).filter(Machine.id == body.machine_id, Machine.org_id == org_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    latest = (
        db.query(SensorReading)
        .filter(SensorReading.machine_id == m.id)
        .order_by(SensorReading.ts.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status.HTTP_409_CONFLICT, "Machine has no sensor readings")
    payload = {
        "air_temperature": latest.air_temperature, "process_temperature": latest.process_temperature,
        "rotational_speed": latest.rotational_speed, "torque": latest.torque,
        "tool_wear": latest.tool_wear, "vibration": latest.vibration,
    }
    return payload, m


@router.post("/failure", response_model=FailurePredictionOut, status_code=201)
def predict_failure(body: FailureIn, request: Request, current: CurrentUserDep, db: DbDep):
    require("create_prediction")(current)
    payload, machine = _resolve_reading(db, current.org_id, body)
    result = pdm.predict_failure(payload)
    try:
        rul = pdm.predict_rul(payload)["rul_hours"]
    except Exception:
        rul = None
    PREDICTIONS_TOTAL.labels(risk_level=result["risk_level"]).inc()
    if machine is not None:
        pred = MaintenancePrediction(
            org_id=current.org_id, machine_id=machine.id,
            model_version=result["model_version"] or "unknown",
            failure_probability=result["failure_probability"], risk_level=result["risk_level"],
            health_score=pdm.health_score(result, rul), rul_hours=rul,
            predicted_modes=result["predicted_modes"], recommendations=result["recommendations"],
            input_snapshot=payload, created_by=current.id,
        )
        db.add(pred)
        audit_log(db, org_id=current.org_id, user_id=current.id, action="prediction_create",
                  resource="maintenance_prediction", resource_id=pred.id,
                  ip=request.client.host if request.client else None)
        db.commit()
    return FailurePredictionOut(**result)


@router.post("/rul", response_model=RulOut, status_code=201)
def predict_rul(body: RulIn, current: CurrentUserDep, db: DbDep):
    require("create_prediction")(current)
    payload, _ = _resolve_reading(db, current.org_id, body)
    try:
        return RulOut(**pdm.predict_rul(payload, body.cycles_elapsed))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@router.get("", response_model=Page[PredictionOut])
def list_predictions(current: CurrentUserDep, db: DbDep, page: PageParams, machine_id: int | None = None):
    q = db.query(MaintenancePrediction).filter(MaintenancePrediction.org_id == current.org_id)
    if machine_id:
        q = q.filter(MaintenancePrediction.machine_id == machine_id)
    total = q.count()
    items = q.order_by(MaintenancePrediction.created_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[PredictionOut](
        items=[PredictionOut.model_validate(p) for p in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


# ---------------- Maintenance requests ----------------

requests_router = APIRouter(prefix="/maintenance-requests", tags=["maintenance-requests"])


@requests_router.get("", response_model=Page[MaintenanceRequestOut])
def list_requests(current: CurrentUserDep, db: DbDep, page: PageParams, status_filter: str | None = None):
    q = db.query(MaintenanceRequest).filter(MaintenanceRequest.org_id == current.org_id)
    if status_filter:
        q = q.filter(MaintenanceRequest.status == status_filter)
    total = q.count()
    items = q.order_by(MaintenanceRequest.created_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[MaintenanceRequestOut](
        items=[MaintenanceRequestOut.model_validate(r) for r in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@requests_router.post("", response_model=MaintenanceRequestOut, status_code=201)
def create_request(payload: MaintenanceRequestCreate, request: Request, current: CurrentUserDep, db: DbDep):
    require("manage_requests")(current)
    if not db.query(Machine).filter(Machine.id == payload.machine_id, Machine.org_id == current.org_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    req = MaintenanceRequest(org_id=current.org_id, created_by=current.id, **payload.model_dump())
    db.add(req)
    audit_log(db, org_id=current.org_id, user_id=current.id, action="maintenance_request_create",
              resource="maintenance_request", resource_id=req.id,
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(req)
    return MaintenanceRequestOut.model_validate(req)


@requests_router.post("/{request_id}/approve", response_model=MaintenanceRequestOut)
def approve_request(request_id: int, request: Request, current: CurrentUserDep, db: DbDep):
    require("approve_requests")(current)
    req = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.id == request_id, MaintenanceRequest.org_id == current.org_id
    ).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if req.status != MaintenanceRequestStatus.OPEN.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Request is '{req.status}', only 'open' can be approved")
    req.status = MaintenanceRequestStatus.APPROVED.value
    req.approved_by = current.id
    audit_log(db, org_id=current.org_id, user_id=current.id, action="maintenance_request_approve",
              resource="maintenance_request", resource_id=req.id,
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(req)
    return MaintenanceRequestOut.model_validate(req)


@requests_router.post("/{request_id}/reject", response_model=MaintenanceRequestOut)
def reject_request(request_id: int, current: CurrentUserDep, db: DbDep):
    require("approve_requests")(current)
    req = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.id == request_id, MaintenanceRequest.org_id == current.org_id
    ).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    req.status = MaintenanceRequestStatus.REJECTED.value
    req.approved_by = current.id
    db.commit()
    db.refresh(req)
    return MaintenanceRequestOut.model_validate(req)


@requests_router.patch("/{request_id}/status", response_model=MaintenanceRequestOut)
def update_status(request_id: int, new_status: str, current: CurrentUserDep, db: DbDep):
    require("manage_requests")(current)
    allowed = [s.value for s in MaintenanceRequestStatus]
    if new_status not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid status. Allowed: {allowed}")
    req = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.id == request_id, MaintenanceRequest.org_id == current.org_id
    ).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    req.status = new_status
    db.commit()
    db.refresh(req)
    return MaintenanceRequestOut.model_validate(req)
