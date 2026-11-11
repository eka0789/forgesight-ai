from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbDep
from app.services.analytics import dashboard_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/production")
def production_report(current: CurrentUserDep, db: DbDep):
    s = dashboard_summary(db, current.org_id)
    return {
        "report": "production",
        "trend": s["production_trend"],
        "machine_status": s["machine_status"],
        "kpis": s["kpis"],
    }


@router.get("/quality")
def quality_report(current: CurrentUserDep, db: DbDep):
    s = dashboard_summary(db, current.org_id)
    return {
        "report": "quality",
        "defect_distribution": s["defect_distribution"],
        "kpis": s["kpis"],
    }


@router.get("/maintenance")
def maintenance_report(current: CurrentUserDep, db: DbDep):
    from app.models.maintenance import MaintenanceRequest

    rows = (
        db.query(MaintenanceRequest)
        .filter(MaintenanceRequest.org_id == current.org_id)
        .order_by(MaintenanceRequest.created_at.desc())
        .limit(50)
        .all()
    )
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_priority[r.priority] = by_priority.get(r.priority, 0) + 1
    return {"report": "maintenance", "by_status": by_status, "by_priority": by_priority,
            "recent": [{"id": r.id, "title": r.title, "status": r.status,
                        "priority": r.priority, "source": r.source} for r in rows]}
