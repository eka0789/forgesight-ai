from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbDep
from app.schemas.dashboard import DashboardSummaryOut
from app.services.analytics import dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard(current: CurrentUserDep, db: DbDep):
    return dashboard_summary(db, current.org_id)
