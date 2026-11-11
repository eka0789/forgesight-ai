"""Shared FastAPI dependencies: auth, RBAC, pagination."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Role -> set of permissions. Keeps authorization logic in ONE place.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.OWNER.value: {
        "read", "manage_users", "manage_machines", "run_inspection",
        "create_prediction", "manage_documents", "use_agent",
        "manage_requests", "approve_requests", "manage_settings",
    },
    Role.ADMIN.value: {
        "read", "manage_users", "manage_machines", "run_inspection",
        "create_prediction", "manage_documents", "use_agent",
        "manage_requests", "approve_requests", "manage_settings",
    },
    Role.ENGINEER.value: {
        "read", "manage_machines", "run_inspection", "create_prediction",
        "manage_documents", "use_agent", "manage_requests",
    },
    Role.OPERATOR.value: {
        "read", "run_inspection", "use_agent",
    },
    Role.VIEWER.value: {"read"},
}


class CurrentUser:
    def __init__(self, user: User, org_id: int):
        self.user = user
        self.org_id = org_id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def id(self) -> int:
        return self.user.id

    def can(self, action: str) -> bool:
        return action in ROLE_PERMISSIONS.get(self.role, set())


def _load_user(token: str | None, db: Session) -> CurrentUser:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or unknown")
    return CurrentUser(user, user.org_id)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> CurrentUser:
    return _load_user(token, db)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require(action: str):
    """Dependency factory enforcing RBAC for an action."""

    def _checker(current: CurrentUserDep) -> CurrentUser:
        if not current.can(action):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{current.role}' is not permitted to perform '{action}'",
            )
        return current

    return _checker


def paginate(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return {"page": page, "page_size": page_size}


PageParams = Annotated[dict, Depends(paginate)]
DbDep = Annotated[Session, Depends(get_db)]
