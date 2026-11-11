from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.models.agent import AgentExecution
from app.schemas.agent import AgentChatIn, ApprovalOut, ExecutionDetailOut, ExecutionOut
from app.schemas.common import Page
from app.services.agent.graph import approve_and_continue, run_agent
from app.services.audit import audit_log

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", status_code=201)
def agent_chat(payload: AgentChatIn, request: Request, current: CurrentUserDep, db: DbDep):
    """Runs the agent graph (planner → tools → validation → response).

    Sensitive tools park the run in `awaiting_approval` (human-in-the-loop)."""
    require("use_agent")(current)
    result = run_agent(db, org_id=current.org_id, user_id=current.id,
                       message=payload.message, conversation_id=payload.conversation_id)
    audit_log(db, org_id=current.org_id, user_id=current.id, action="agent_run",
              resource="agent_execution", resource_id=result["execution_id"],
              detail={"planner": result["planner"], "status": result["status"]},
              ip=request.client.host if request.client else None)
    db.commit()
    return result


@router.get("/executions", response_model=Page[ExecutionOut])
def list_executions(current: CurrentUserDep, db: DbDep, page: PageParams):
    q = db.query(AgentExecution).filter(AgentExecution.org_id == current.org_id)
    total = q.count()
    items = q.order_by(AgentExecution.started_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[ExecutionOut](
        items=[ExecutionOut.model_validate(e) for e in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.get("/executions/{execution_id}", response_model=ExecutionDetailOut)
def get_execution(execution_id: int, current: CurrentUserDep, db: DbDep):
    e = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id, AgentExecution.org_id == current.org_id
    ).first()
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    return ExecutionDetailOut.model_validate(e)


class ApprovalIn(BaseModel):
    approve: bool


@router.post("/approvals/{execution_id}", response_model=ApprovalOut)
def approval(execution_id: int, payload: ApprovalIn, request: Request, current: CurrentUserDep, db: DbDep):
    """Human approval endpoint for pending sensitive tool executions."""
    require("approve_requests")(current)
    e = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id, AgentExecution.org_id == current.org_id
    ).first()
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    if e.status != "awaiting_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Execution status is '{e.status}'")
    pending = (e.result or {}).get("pending_tool") or {}
    result = approve_and_continue(db, execution=e, approver_id=current.id, approve=payload.approve)
    audit_log(db, org_id=current.org_id, user_id=current.id,
              action="agent_approval_granted" if payload.approve else "agent_approval_rejected",
              resource="agent_execution", resource_id=e.id,
              detail={"tool": pending.get("tool")},
              ip=request.client.host if request.client else None)
    db.commit()
    return ApprovalOut(
        execution_id=e.id, status=result["status"], tool=pending.get("tool"),
        args=pending.get("args"),
        message="Approved and executed." if payload.approve else "Rejected — no action taken.",
    )


@router.get("/tools")
def list_tools(current: CurrentUserDep):
    """Tool catalog incl. which tools require human approval."""
    from app.services.agent.tools import TOOLS

    return {
        "tools": [
            {
                "name": name, "description": spec["description"],
                "requires_approval": spec["needs_approval"],
                "args_schema": list(spec["args"].model_fields.keys()),
            }
            for name, spec in TOOLS.items()
        ],
        "max_iterations": 8,
        "note": "Sensitive tools require human approval before execution.",
    }
