"""Audit trail helper — one place to record sensitive actions."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def audit_log(
    db: Session,
    *,
    org_id: int | None,
    user_id: int | None,
    action: str,
    resource: str,
    resource_id: str | int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id is not None else None,
            detail=detail,
            ip=ip,
        )
    )
    # commit is left to the caller (keeps transactional boundaries explicit)
