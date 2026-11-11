"""Dashboard/analytics aggregations (Module A) — real SQL over real data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentExecution
from app.models.inspection import DetectedDefect, Inspection
from app.models.machine import Machine
from app.models.maintenance import MaintenancePrediction, MaintenanceRequest
from app.models.organization import Organization
from app.services.pdm import inference as pdm


def dashboard_summary(db: Session, org_id: int) -> dict:
    now = datetime.now(timezone.utc)

    inspections_q = db.query(Inspection).filter(Inspection.org_id == org_id)
    total_inspections = inspections_q.filter(Inspection.status == "completed").count()
    total_defects = int(
        inspections_q.filter(Inspection.status == "completed")
        .with_entities(sa_func.coalesce(sa_func.sum(Inspection.defect_count), 0))
        .scalar()
        or 0
    )
    avg_inference = (
        inspections_q.filter(Inspection.status == "completed")
        .with_entities(sa_func.avg(Inspection.processing_ms))
        .scalar()
    )
    completed_with_result = total_inspections
    defect_rate = (total_defects / completed_with_result) if completed_with_result else 0.0

    machines = db.query(Machine).filter(Machine.org_id == org_id, Machine.is_active.is_(True)).all()
    health_scores: list[float] = []
    predicted_events = 0
    for m in machines:
        last_pred = (
            db.query(MaintenancePrediction)
            .filter(MaintenancePrediction.machine_id == m.id)
            .order_by(MaintenancePrediction.created_at.desc())
            .first()
        )
        if last_pred:
            health_scores.append(last_pred.health_score)
            if last_pred.risk_level in ("high", "critical"):
                predicted_events += 1
        else:
            base = {"healthy": 92.0, "warning": 70.0, "critical": 45.0, "offline": 0.0}.get(m.status, 80.0)
            health_scores.append(base)

    open_requests = (
        db.query(MaintenanceRequest)
        .filter(
            MaintenanceRequest.org_id == org_id,
            MaintenanceRequest.status.in_(["open", "approved", "in_progress"]),
        )
        .count()
    )

    # 14-day production trend
    start_date = (now - timedelta(days=13)).date()
    rows = (
        db.query(
            sa_func.date(Inspection.created_at),
            sa_func.count(Inspection.id),
            sa_func.coalesce(sa_func.sum(Inspection.defect_count), 0),
        )
        .filter(
            Inspection.org_id == org_id,
            Inspection.status == "completed",
            Inspection.created_at >= start_date,
        )
        .group_by(sa_func.date(Inspection.created_at))
        .all()
    )
    by_date = {str(r[0]): {"inspections": int(r[1]), "defects": int(r[2])} for r in rows}
    trend = []
    for i in range(14):
        d = start_date + timedelta(days=i)
        v = by_date.get(str(d), {"inspections": 0, "defects": 0})
        trend.append({"date": d.isoformat(), **v})

    # Defect distribution
    dist_rows = (
        db.query(DetectedDefect.label, sa_func.count(DetectedDefect.id))
        .filter(DetectedDefect.org_id == org_id)
        .group_by(DetectedDefect.label)
        .order_by(sa_func.count(DetectedDefect.id).desc())
        .all()
    )
    defect_distribution = [{"label": r[0], "count": int(r[1])} for r in dist_rows]

    # Machine status distribution
    status_rows = (
        db.query(Machine.status, sa_func.count(Machine.id))
        .filter(Machine.org_id == org_id, Machine.is_active.is_(True))
        .group_by(Machine.status)
        .all()
    )
    machine_status = [{"status": r[0], "count": int(r[1])} for r in status_rows]

    # Model metrics snapshot
    from app.models.mlops import MLModel

    model_metrics = []
    for m in db.query(MLModel).all()[:6]:
        prod = next((v for v in m.versions if v.status == "production"), None) or (
            m.versions[0] if m.versions else None
        )
        if prod and prod.metrics:
            model_metrics.append({"model_name": m.name, "task": m.task, "metrics": prod.metrics})

    # Recent activity
    recent: list[dict] = []
    for i in inspections_q.order_by(Inspection.created_at.desc()).limit(6):
        recent.append(
            {"ts": str(i.created_at), "kind": "inspection",
             "title": f"{i.kind} inspection — {i.filename}",
             "detail": f"{i.defect_count} defect(s) · {i.status}"}
        )
    pred_rows = (
        db.query(MaintenancePrediction)
        .filter(MaintenancePrediction.org_id == org_id)
        .order_by(MaintenancePrediction.created_at.desc())
        .limit(4)
        .all()
    )
    for p in pred_rows:
        recent.append(
            {"ts": str(p.created_at), "kind": "prediction",
             "title": f"Machine #{p.machine_id} risk {p.risk_level}",
             "detail": f"p(failure)={p.failure_probability:.2f}"}
        )
    agent_rows = (
        db.query(AgentExecution)
        .filter(AgentExecution.org_id == org_id)
        .order_by(AgentExecution.started_at.desc())
        .limit(3)
        .all()
    )
    for a in agent_rows:
        recent.append(
            {"ts": str(a.started_at), "kind": "agent",
             "title": f"Agent run ({a.planner}) — {a.status}", "detail": a.input[:60]}
        )
    recent.sort(key=lambda x: x["ts"], reverse=True)

    pdm.artifacts.load()
    artifacts_ok = "ok" if (pdm.artifacts.failure_meta or pdm.artifacts.rul_meta) else "missing"
    llm_mode = "external" if settings.llm_available else "mock-demo"
    org = db.get(Organization, org_id)
    is_demo_data = bool(org.is_demo) if org else False

    return {
        "kpis": {
            "total_inspections": total_inspections,
            "total_defects": total_defects,
            "defect_detection_rate": round(defect_rate, 4),
            "avg_machine_health": round(sum(health_scores) / len(health_scores), 1) if health_scores else 0.0,
            "predicted_maintenance_events": predicted_events,
            "avg_inference_ms": round(float(avg_inference), 1) if avg_inference else None,
            "open_maintenance_requests": open_requests,
        },
        "production_trend": trend,
        "defect_distribution": defect_distribution,
        "machine_status": machine_status,
        "model_metrics": model_metrics,
        "recent_activity": recent[:10],
        "ai_system_health": {
            "llm_provider": settings.llm_provider,
            "llm_mode": llm_mode,
            "embedding_provider": settings.embedding_provider,
            "artifacts_status": artifacts_ok,
            "status": "healthy" if artifacts_ok == "ok" else "degraded",
        },
        "is_demo_data": is_demo_data,
    }
