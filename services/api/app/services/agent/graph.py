"""Agent graph: intent → plan → tool execution (with approval gate) → validate → respond.

LangGraph-style node/edge structure implemented dependency-free so it runs and
tests everywhere; the node functions are pure state transforms, making a swap
to the `langgraph` library a drop-in adapter exercise (documented in docs/).

Tool policy: per-call timeout (TOOL_TIMEOUT_SECONDS) + automatic retry
(TOOL_MAX_ATTEMPTS); failures become structured tool-log entries, never crashes.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentExecution, AgentToolLog
from app.models.ai import AiConversation, AiMessage
from app.models.machine import Machine
from app.services.agent.tools import MAX_ITERATIONS, TOOL_TIMEOUT_SECONDS, TOOLS, ToolCtx

INTENT_RULES: list[tuple[str, str]] = [
    (r"(machine|mesin|status|health|kesehatan)", "get_machine_status"),
    (r"(predict|prediksi|failure|gagal|breakdown)", "predict_machine_failure"),
    (r"(inspect|inspeksi|defect|cacat|quality|kualitas)", "get_inspection_results"),
    (r"(incident|laporan|report)", "generate_incident_report"),
    (r"(maintenance|perbaikan|repair|request)", "create_maintenance_request"),
    (r"(production|produksi|trend|analytics|kpi)", "get_production_analytics"),
    (r"(document|dokumen|manual|knowledge|spesifikasi|how)", "search_knowledge_base"),
]

_TOOL_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fsg-agent-tool")
TOOL_MAX_ATTEMPTS = 2

SYSTEM_PLANNER = (
    "You are ForgeSight AI's industrial operations agent planner. Select tools from: "
    + ", ".join(TOOLS.keys())
    + '. Reply with STRICT JSON: {"intent": "<short>", "tools": ["<tool>", ...]} '
    "using at most 3 tools. No prose."
)


def _parse_intent_llm(message: str) -> dict | None:
    from app.services.knowledge.llm import get_llm

    if not settings.llm_available:
        return None
    try:
        raw = get_llm().complete(SYSTEM_PLANNER, message, max_tokens=150, temperature=0.0)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        tools = [t for t in (data.get("tools") or []) if t in TOOLS][:3]
        return {"intent": str(data.get("intent", "general")), "tools": tools or ["get_machine_status"]}
    except Exception:
        return None


def _parse_intent_rules(message: str) -> dict:
    low = message.lower()
    selected: list[str] = []
    for pattern, tool in INTENT_RULES:
        if re.search(pattern, low):
            if tool not in selected:
                selected.append(tool)
        if len(selected) >= 3:
            break
    if not selected:
        selected = ["search_knowledge_base", "get_machine_status"]
    # A maintenance question most likely also wants current status first.
    if "create_maintenance_request" in selected and "get_machine_status" not in selected:
        selected = ["get_machine_status"] + selected
    return {"intent": "rule_based", "tools": selected}


def _respond(planner: str, message: str, intent: str, tool_results: list[dict]) -> str:
    """LLM synthesis when available; otherwise a transparent rule-based summary."""
    from app.services.knowledge.llm import get_llm

    if planner == "llm" and settings.llm_available:
        tool_summary = json.dumps(tool_results, default=str)[:6000]
        system = (
            "You are ForgeSight AI's operations assistant. Summarize the tool results for the "
            "user's request. Ground every claim in the tool results (no invented facts). "
            "Structure: 1) direct answer, 2) key evidence, 3) recommended next steps. Be concise."
        )
        try:
            return get_llm().complete(system, f"User request: {message}\n\nTool results:\n{tool_summary}", max_tokens=800)
        except Exception:
            pass
    lines = [f"**Intent**: {intent}", ""]
    for tr in tool_results:
        tool = tr["tool"]
        data = tr["result"]
        if tr["status"] == "error":
            lines.append(f"### {tool}\n- status: failed — {data}")
        else:
            preview = json.dumps(data, default=str, ensure_ascii=False)
            lines.append(f"### {tool}\n```json\n{preview[:1200]}\n```")
    lines.append("")
    lines.append("_Local rule-based responder (no external LLM key configured) — tool data above is real._")
    return "\n".join(lines)


def _execute_tool(ctx: ToolCtx, name: str, args_dict: dict) -> dict:
    """Runs a tool with the configured per-call timeout (enforced via a worker
    thread so a hung tool cannot block the event loop / request)."""
    spec = TOOLS[name]
    args_model = spec["args"](**args_dict)
    future = _TOOL_POOL.submit(spec["fn"], ctx, args_model)
    try:
        return future.result(timeout=TOOL_TIMEOUT_SECONDS)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"tool '{name}' exceeded {TOOL_TIMEOUT_SECONDS}s timeout") from exc


def run_agent(db: Session, *, org_id: int, user_id: int, message: str,
              conversation_id: int | None) -> dict:
    """Runs the graph synchronously (called from the API router). Returns the
    final execution state for the client. Approval-gated tools park the
    execution in awaiting_approval."""
    started = datetime.now(timezone.utc)
    if conversation_id:
        conv = db.get(AiConversation, conversation_id)
        if conv is None or conv.org_id != org_id or conv.kind != "agent":
            conv = None
    else:
        conv = None
    if conv is None:
        conv = AiConversation(org_id=org_id, user_id=user_id, kind="agent",
                              title=message[:60] or "Agent session")
        db.add(conv)
        db.flush()

    db.add(AiMessage(conversation_id=conv.id, role="user", content=message))
    db.flush()

    execution = AgentExecution(
        org_id=org_id, user_id=user_id, conversation_id=conv.id, input=message,
        status="running", started_at=started,
    )
    db.add(execution)
    db.flush()

    ctx = ToolCtx(db, org_id, user_id)

    intent_data = _parse_intent_llm(message) or _parse_intent_rules(message)
    planner = "llm" if intent_data["intent"] != "rule_based" else "rule_based"
    execution.planner = planner
    execution.iterations = 0

    tool_results: list[dict] = []
    awaiting: dict | None = None
    for tool_name in intent_data["tools"][:MAX_ITERATIONS]:
        execution.iterations += 1
        spec = TOOLS[tool_name]
        args_dict: dict = {}
        # Minimal arg extraction for the two most common tools (rule planner).
        if tool_name == "search_knowledge_base":
            args_dict = {"query": message[:300]}
        if tool_name in ("predict_machine_failure", "create_maintenance_request", "generate_incident_report", "analyze_defect"):
            m = re.search(r"(?:machine|mesin)[\s_-]*(?:id)?[\s:]*#?(\d+)", message.lower())
            if m:
                args_dict["machine_id"] = int(m.group(1))
            if tool_name == "analyze_defect":
                m2 = re.search(r"inspection[\s_-]*(?:id)?[\s:]*#?(\d+)", message.lower())
                if m2:
                    args_dict = {"inspection_id": int(m2.group(1))}
            if tool_name == "create_maintenance_request":
                args_dict.setdefault("title", f"Agent-initiated: {message[:80]}")
            if tool_name == "generate_incident_report":
                args_dict.setdefault("summary", message[:300])
        if "machine_id" not in args_dict and tool_name in (
            "predict_machine_failure", "generate_incident_report", "create_maintenance_request",
        ):
            m0 = db.query(Machine).filter(Machine.org_id == org_id).order_by(Machine.id).first()
            if m0:
                args_dict["machine_id"] = m0.id

        t0 = time.perf_counter()
        if spec["needs_approval"] and spec["permission"] not in _forbidden():
            # Human-in-the-loop gate — never auto-execute sensitive tools.
            awaiting = {"tool": tool_name, "args": args_dict}
            db.add(AgentToolLog(
                execution_id=execution.id, tool_name=tool_name, args=args_dict,
                status="awaiting_approval", duration_ms=int((time.perf_counter() - t0) * 1000),
            ))
            break
        # Timeout + retry policy: one automatic retry on transient failure.
        result: dict | None = None
        error: str | None = None
        for attempt in range(1, TOOL_MAX_ATTEMPTS + 1):
            try:
                result = _execute_tool(ctx, tool_name, args_dict)
                error = None
                break
            except Exception as exc:  # noqa: BLE001 — tool failures are data, not crashes
                error = f"{exc.__class__.__name__}: {exc}"
                if attempt < TOOL_MAX_ATTEMPTS:
                    db.rollback()  # clear any partial transaction from the failed tool
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if result is not None:
            status = "error" if (isinstance(result, dict) and result.get("error")) else "ok"
            db.add(AgentToolLog(
                execution_id=execution.id, tool_name=tool_name, args=args_dict,
                result=result, status=status, duration_ms=duration_ms,
            ))
            tool_results.append({"tool": tool_name, "status": status, "result": result})
        else:
            db.add(AgentToolLog(
                execution_id=execution.id, tool_name=tool_name, args=args_dict,
                result={"error": error}, status="error", duration_ms=duration_ms,
            ))
            tool_results.append({"tool": tool_name, "status": "error", "result": error})

    if awaiting:
        execution.status = "awaiting_approval"
        execution.result = {"pending_tool": awaiting, "tool_results": tool_results,
                            "message": "Tool requires human approval before execution."}
        db.commit()
        db.refresh(execution)
        return {
            "execution_id": execution.id, "conversation_id": conv.id,
            "status": execution.status, "planner": planner,
            "iterations": execution.iterations,
            "tool_results": tool_results,
            "approval_required": awaiting,
            "message": execution.result["message"],
        }

    response_text = _respond(planner, message, intent_data["intent"], tool_results)
    db.add(AiMessage(
        conversation_id=conv.id, role="assistant", content=response_text,
        meta={"planner": planner, "tools": [t["tool"] for t in tool_results]},
    ))
    execution.status = "completed"
    execution.result = {"intent": intent_data["intent"], "tool_results": tool_results}
    execution.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(execution)
    return {
        "execution_id": execution.id, "conversation_id": conv.id,
        "status": execution.status, "planner": planner,
        "iterations": execution.iterations, "answer": response_text,
        "tool_results": tool_results,
    }


def approve_and_continue(db: Session, *, execution: AgentExecution, approver_id: int, approve: bool) -> dict:
    """Executes or rejects the pending approval-gated tool, then finishes the run."""
    pending = ((execution.result or {}).get("pending_tool") or {})
    tool_results = (execution.result or {}).get("tool_results", [])
    tool_name = pending.get("tool")
    conv = db.get(AiConversation, execution.conversation_id) if execution.conversation_id else None

    if not approve or not tool_name:
        execution.status = "completed"
        execution.result = {"tool_results": tool_results, "approval": "rejected"}
        execution.finished_at = datetime.now(timezone.utc)
        if conv:
            db.add(AiMessage(conversation_id=conv.id, role="assistant",
                             content="Action was **rejected** by an approver — no changes were made.",
                             meta={"approval": "rejected"}))
        db.commit()
        return {"status": "completed", "approval": "rejected", "execution_id": execution.id}

    ctx = ToolCtx(db, execution.org_id, approver_id)
    t0 = time.perf_counter()
    try:
        result = _execute_tool(ctx, tool_name, pending.get("args") or {})
        status = "error" if (isinstance(result, dict) and result.get("error")) else "ok"
        db.add(AgentToolLog(execution_id=execution.id, tool_name=tool_name,
                            args=pending.get("args"), result=result, status=status,
                            duration_ms=int((time.perf_counter() - t0) * 1000)))
        tool_results.append({"tool": tool_name, "status": status, "result": result})
        text = _respond(execution.planner, execution.input, "approved-action", tool_results)
    except Exception as exc:
        db.add(AgentToolLog(execution_id=execution.id, tool_name=tool_name,
                            args=pending.get("args"), result={"error": str(exc)}, status="error",
                            duration_ms=int((time.perf_counter() - t0) * 1000)))
        tool_results.append({"tool": tool_name, "status": "error", "result": str(exc)})
        text = f"Approved tool `{tool_name}` failed: {exc}"

    execution.status = "completed"
    execution.result = {"tool_results": tool_results, "approval": "approved"}
    execution.finished_at = datetime.now(timezone.utc)
    if conv:
        db.add(AiMessage(conversation_id=conv.id, role="assistant", content=text,
                         meta={"approval": "approved"}))
    db.commit()
    return {"status": "completed", "approval": "approved", "execution_id": execution.id, "answer": text}


def _forbidden() -> set[str]:
    """Set of tool names that must NEVER run even with approval (reserved)."""
    return set()
