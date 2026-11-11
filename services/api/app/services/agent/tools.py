"""Agent tool registry with Pydantic-validated arguments and permissions.

Sensitive tools (create_maintenance_request) REQUIRE human approval — they are
never executed directly by the graph loop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.enums import RequestPriority
from app.models.inspection import DetectedDefect, Inspection
from app.models.knowledge import Document
from app.models.machine import Machine, SensorReading
from app.models.maintenance import MaintenancePrediction, MaintenanceRequest
from app.services import analytics
from app.services.pdm import inference as pdm


class ToolCtx:
    def __init__(self, db: Session, org_id: int, user_id: int):
        self.db = db
        self.org_id = org_id
        self.user_id = user_id


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class MachineStatusArgs(BaseModel):
    machine_id: int | None = None


class InspectionResultsArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    machine_id: int | None = None


class PredictFailureArgs(BaseModel):
    machine_id: int


class AnalyzeDefectArgs(BaseModel):
    inspection_id: int


class IncidentReportArgs(BaseModel):
    machine_id: int
    summary: str = Field(min_length=3, max_length=2000)


class MaintenanceRequestArgs(BaseModel):
    machine_id: int
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    priority: str = "medium"


class ProductionAnalyticsArgs(BaseModel):
    days: int = Field(default=7, ge=1, le=90)


def _org_machine(db: Session, ctx: ToolCtx, machine_id: int) -> Machine:
    return db.query(Machine).filter(Machine.id == machine_id, Machine.org_id == ctx.org_id).first()


def tool_search_knowledge_base(ctx: ToolCtx, args: SearchKnowledgeArgs) -> dict:
    from app.services.knowledge.retriever import hybrid_search

    results, method = hybrid_search(ctx.db, ctx.org_id, args.query, top_k=args.top_k)
    doc_count = ctx.db.query(Document).filter(Document.org_id == ctx.org_id, Document.status == "indexed").count()
    return {
        "retrieval_method": method,
        "indexed_documents": doc_count,
        "results": [
            {"title": r["document_title"], "page": r["page_number"], "content": r["content"][:400]}
            for r in results
        ],
    }


def tool_get_machine_status(ctx: ToolCtx, args: MachineStatusArgs) -> dict:
    q = ctx.db.query(Machine).filter(Machine.org_id == ctx.org_id, Machine.is_active.is_(True))
    if args.machine_id:
        q = q.filter(Machine.id == args.machine_id)
    machines = q.all()
    out = []
    for m in machines:
        latest = (
            ctx.db.query(SensorReading)
            .filter(SensorReading.machine_id == m.id)
            .order_by(SensorReading.ts.desc())
            .first()
        )
        last_pred = (
            ctx.db.query(MaintenancePrediction)
            .filter(MaintenancePrediction.machine_id == m.id)
            .order_by(MaintenancePrediction.created_at.desc())
            .first()
        )
        out.append({
            "id": m.id, "code": m.code, "name": m.name, "status": m.status,
            "latest_reading": {
                "ts": str(latest.ts), "air_temperature": latest.air_temperature,
                "process_temperature": latest.process_temperature,
                "rotational_speed": latest.rotational_speed, "torque": latest.torque,
                "tool_wear": latest.tool_wear,
            } if latest else None,
            "last_health_score": last_pred.health_score if last_pred else None,
            "last_failure_probability": last_pred.failure_probability if last_pred else None,
        })
    return {"machines": out, "count": len(out)}


def tool_get_inspection_results(ctx: ToolCtx, args: InspectionResultsArgs) -> dict:
    q = ctx.db.query(Inspection).filter(Inspection.org_id == ctx.org_id)
    if args.machine_id:
        q = q.filter(Inspection.machine_id == args.machine_id)
    rows = q.order_by(Inspection.created_at.desc()).limit(args.limit).all()
    return {
        "inspections": [
            {
                "id": i.id, "kind": i.kind, "filename": i.filename, "status": i.status,
                "result": i.result, "defect_count": i.defect_count,
                "method_used": i.method_used, "created_at": str(i.created_at),
            }
            for i in rows
        ],
        "count": len(rows),
    }


def tool_predict_machine_failure(ctx: ToolCtx, args: PredictFailureArgs) -> dict:
    machine = _org_machine(ctx.db, ctx, args.machine_id)
    if not machine:
        return {"error": f"machine {args.machine_id} not found in this organization"}
    latest = (
        ctx.db.query(SensorReading)
        .filter(SensorReading.machine_id == machine.id)
        .order_by(SensorReading.ts.desc())
        .first()
    )
    if not latest:
        return {"error": f"no sensor readings available for machine {machine.code}"}
    payload = {
        "air_temperature": latest.air_temperature, "process_temperature": latest.process_temperature,
        "rotational_speed": latest.rotational_speed, "torque": latest.torque,
        "tool_wear": latest.tool_wear, "vibration": latest.vibration,
    }
    result = pdm.predict_failure(payload)
    rul = None
    try:
        rul = pdm.predict_rul(payload)["rul_hours"]
    except Exception:
        rul = None
    pred = MaintenancePrediction(
        org_id=ctx.org_id, machine_id=machine.id, model_version=result["model_version"] or "unknown",
        failure_probability=result["failure_probability"], risk_level=result["risk_level"],
        health_score=pdm.health_score(result, rul), rul_hours=rul,
        predicted_modes=result["predicted_modes"], recommendations=result["recommendations"],
        input_snapshot=payload, created_by=ctx.user_id,
    )
    ctx.db.add(pred)
    ctx.db.commit()
    ctx.db.refresh(pred)
    return {
        "machine": {"id": machine.id, "code": machine.code, "name": machine.name},
        "prediction_id": pred.id,
        **result,
        "rul_hours": rul,
        "health_score": pred.health_score,
    }


def tool_analyze_defect(ctx: ToolCtx, args: AnalyzeDefectArgs) -> dict:
    insp = ctx.db.query(Inspection).filter(Inspection.id == args.inspection_id, Inspection.org_id == ctx.org_id).first()
    if not insp:
        return {"error": f"inspection {args.inspection_id} not found in this organization"}
    defects = ctx.db.query(DetectedDefect).filter(DetectedDefect.inspection_id == insp.id).all()
    by_label: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    for d in defects:
        by_label[d.label] = by_label.get(d.label, 0) + 1
        by_sev[d.severity or "medium"] = by_sev.get(d.severity or "medium", 0) + 1
    return {
        "inspection_id": insp.id, "result": insp.result, "defect_count": len(defects),
        "by_label": by_label, "by_severity": by_sev,
        "avg_confidence": insp.avg_confidence, "method_used": insp.method_used,
    }


def tool_generate_incident_report(ctx: ToolCtx, args: IncidentReportArgs) -> dict:
    machine = _org_machine(ctx.db, ctx, args.machine_id)
    if not machine:
        return {"error": f"machine {args.machine_id} not found in this organization"}
    from app.models.audit import Notification

    recent_inspections = (
        ctx.db.query(Inspection).filter(Inspection.machine_id == machine.id)
        .order_by(Inspection.created_at.desc()).limit(10).all()
    )
    defect_total = sum(i.defect_count for i in recent_inspections)
    report = (
        f"# Incident Report — {machine.name} ({machine.code})\n\n"
        f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}\n"
        f"- Machine status: {machine.status}\n"
        f"- Summary: {args.summary}\n"
        f"- Recent inspections: {len(recent_inspections)} (defects found: {defect_total})\n\n"
        "## Recommended actions\n"
        "1. Validate the summary above with on-site inspection.\n"
        "2. Review latest predictive-maintenance prediction for this machine.\n"
        "3. If confirmed, create a maintenance request (requires approval).\n"
    )
    ctx.db.add(Notification(org_id=ctx.org_id, type="incident", title=f"Incident report: {machine.code}", body=args.summary[:200]))
    ctx.db.commit()
    return {"report_markdown": report, "machine": machine.code}


def tool_create_maintenance_request(ctx: ToolCtx, args: MaintenanceRequestArgs) -> dict:
    machine = _org_machine(ctx.db, ctx, args.machine_id)
    if not machine:
        return {"error": f"machine {args.machine_id} not found in this organization"}
    req = MaintenanceRequest(
        org_id=ctx.org_id, machine_id=machine.id, title=args.title,
        description=args.description, priority=args.priority if args.priority in [p.value for p in RequestPriority] else "medium",
        status="open", source="agent", created_by=ctx.user_id,
    )
    ctx.db.add(req)
    ctx.db.commit()
    ctx.db.refresh(req)
    return {
        "request_id": req.id, "machine": machine.code, "title": req.title,
        "priority": req.priority, "status": req.status,
    }


def tool_get_production_analytics(ctx: ToolCtx, args: ProductionAnalyticsArgs) -> dict:
    summary = analytics.dashboard_summary(ctx.db, ctx.org_id)
    return {
        "kpis": summary["kpis"],
        "production_trend": summary["production_trend"][-args.days:],
        "machine_status": summary["machine_status"],
    }


ToolSpec = dict[str, Any]

TOOLS: dict[str, ToolSpec] = {
    "search_knowledge_base": {
        "description": "Search industrial knowledge base documents (RAG hybrid retrieval).",
        "args": SearchKnowledgeArgs, "fn": tool_search_knowledge_base,
        "needs_approval": False, "permission": "use_agent",
    },
    "get_machine_status": {
        "description": "Get machine list with status, latest sensor readings and last health score.",
        "args": MachineStatusArgs, "fn": tool_get_machine_status,
        "needs_approval": False, "permission": "use_agent",
    },
    "get_inspection_results": {
        "description": "List recent vision inspection results, optionally per machine.",
        "args": InspectionResultsArgs, "fn": tool_get_inspection_results,
        "needs_approval": False, "permission": "use_agent",
    },
    "predict_machine_failure": {
        "description": "Run failure prediction for a machine from its latest sensor reading (persisted).",
        "args": PredictFailureArgs, "fn": tool_predict_machine_failure,
        "needs_approval": False, "permission": "use_agent",
    },
    "analyze_defect": {
        "description": "Analyze a specific inspection: defect labels, severity distribution, confidence.",
        "args": AnalyzeDefectArgs, "fn": tool_analyze_defect,
        "needs_approval": False, "permission": "use_agent",
    },
    "generate_incident_report": {
        "description": "Generate a structured incident report (markdown) for a machine and notify the team.",
        "args": IncidentReportArgs, "fn": tool_generate_incident_report,
        "needs_approval": False, "permission": "use_agent",
    },
    "create_maintenance_request": {
        "description": "Create a maintenance request. REQUIRES HUMAN APPROVAL before execution.",
        "args": MaintenanceRequestArgs, "fn": tool_create_maintenance_request,
        "needs_approval": True, "permission": "use_agent",
    },
    "get_production_analytics": {
        "description": "Aggregate production KPIs, trends and machine status distribution.",
        "args": ProductionAnalyticsArgs, "fn": tool_get_production_analytics,
        "needs_approval": False, "permission": "use_agent",
    },
}

MAX_ITERATIONS = 8
TOOL_TIMEOUT_SECONDS = 30
