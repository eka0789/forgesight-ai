from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text as sa_text

from app import __version__
from app.api.deps import CurrentUserDep, DbDep
from app.core.config import settings
from app.schemas.common import HealthStatus
from app.services.mlops.drift import drift_report

router = APIRouter(tags=["monitoring"])

_START_TS = time.time()


@router.get("/monitoring/health", response_model=HealthStatus)
def health(db: DbDep):
    db_status = "up"
    try:
        db.execute(sa_text("SELECT 1"))
    except Exception:
        db_status = "down"

    redis_status = "down"
    try:
        from app.core.rate_limit import limiter

        if limiter._redis is not None:
            limiter._redis.ping()
            redis_status = "up"
        else:
            redis_status = "fallback-in-memory"
    except Exception:
        pass

    artifacts = "ok" if (settings.resolved_artifacts_dir / "pdm").exists() else "missing"

    return HealthStatus(
        status="healthy" if db_status == "up" else "degraded",
        database=db_status,
        redis=redis_status,
        storage=settings.storage_backend,
        artifacts=artifacts,
        llm_provider=settings.llm_provider if settings.llm_available else "mock-demo",
        embedding_provider=settings.embedding_provider,
        version=__version__,
    )


@router.get("/monitoring/metrics")
def metrics_snapshot(current: CurrentUserDep, db: DbDep):
    from app.models.inspection import Inspection
    from app.models.knowledge import Document
    from app.models.machine import Machine
    from app.models.maintenance import MaintenancePrediction

    org = current.org_id
    return {
        "uptime_seconds": round(time.time() - _START_TS, 1),
        "ts": datetime.now(timezone.utc).isoformat(),
        "org": {
            "machines_active": db.query(Machine).filter(Machine.org_id == org, Machine.is_active.is_(True)).count(),
            "inspections_total": db.query(Inspection).filter(Inspection.org_id == org).count(),
            "inspections_failed": db.query(Inspection).filter(Inspection.org_id == org, Inspection.status == "failed").count(),
            "predictions_total": db.query(MaintenancePrediction).filter(MaintenancePrediction.org_id == org).count(),
            "documents_indexed": db.query(Document).filter(Document.org_id == org, Document.status == "indexed").count(),
            "documents_failed": db.query(Document).filter(Document.org_id == org, Document.status == "failed").count(),
        },
        "prometheus": "/metrics (internal, scrape target)",
    }


@router.get("/monitoring/drift")
def drift(current: CurrentUserDep, db: DbDep, days: int = 7):
    return drift_report(db, current.org_id, days=days)
