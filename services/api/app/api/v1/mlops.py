from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, DbDep, PageParams
from app.models.mlops import MLModel, ModelMetric
from app.models.mlops_datasets import MLDataset, MLExperiment
from app.schemas.common import Page
from app.schemas.mlops import DatasetOut, ExperimentOut, ModelOut

router = APIRouter(prefix="/models", tags=["mlops"])


@router.get("", response_model=Page[ModelOut])
def list_models(current: CurrentUserDep, db: DbDep, page: PageParams):
    q = db.query(MLModel)
    total = q.count()
    items = q.order_by(MLModel.name).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[ModelOut](
        items=[ModelOut.model_validate(m) for m in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.get("/{model_id}", response_model=ModelOut)
def get_model(model_id: int, current: CurrentUserDep, db: DbDep):
    m = db.get(MLModel, model_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    return ModelOut.model_validate(m)


@router.get("/{model_id}/metrics")
def model_metrics(model_id: int, current: CurrentUserDep, db: DbDep):
    m = db.get(MLModel, model_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    rows = (
        db.query(ModelMetric)
        .join(ModelMetric.model_version)
        .filter(ModelMetric.model_version_id.in_([v.id for v in m.versions]))
        .all()
        if m.versions else []
    )
    return {
        "model_id": model_id,
        "versions": [
            {"version": v.version, "status": v.status, "framework": v.framework,
             "metrics": v.metrics, "params": v.params}
            for v in m.versions
        ],
        "metric_rows": [
            {"version_id": r.model_version_id, "split": r.split, "name": r.name, "value": r.value}
            for r in rows
        ],
    }


experiments_router = APIRouter(prefix="/experiments", tags=["mlops"])


@experiments_router.get("", response_model=Page[ExperimentOut])
def list_experiments(current: CurrentUserDep, db: DbDep, page: PageParams, kind: str | None = None):
    q = db.query(MLExperiment)
    if kind:
        q = q.filter(MLExperiment.kind == kind)
    total = q.count()
    items = q.order_by(MLExperiment.started_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[ExperimentOut](
        items=[ExperimentOut.model_validate(e) for e in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


datasets_router = APIRouter(prefix="/datasets", tags=["mlops"])


@datasets_router.get("", response_model=Page[DatasetOut])
def list_datasets(current: CurrentUserDep, db: DbDep, page: PageParams):
    q = db.query(MLDataset)
    total = q.count()
    items = q.order_by(MLDataset.name).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[DatasetOut](
        items=[DatasetOut.model_validate(d) for d in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )
