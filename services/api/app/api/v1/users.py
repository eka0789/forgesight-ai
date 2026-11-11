from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.core.enums import Role
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.common import Page
from app.services.audit import audit_log

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    role: str = "viewer"


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


@router.get("", response_model=Page[UserOut])
def list_users(current: CurrentUserDep, db: DbDep, page: PageParams):
    require("manage_users")(current)
    q = db.query(User).filter(User.org_id == current.org_id)
    total = q.count()
    items = q.order_by(User.id).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in items],
        total=total, pages=max(1, -(-total // page["page_size"])),
        page=page["page"], page_size=page["page_size"],
    )


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreateIn, request: Request, current: CurrentUserDep, db: DbDep):
    require("manage_users")(current)
    if payload.role not in [r.value for r in Role] or payload.role == Role.OWNER.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        org_id=current.org_id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    audit_log(db, org_id=current.org_id, user_id=current.id, action="user_create",
              resource="user", resource_id=user.id, ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdateIn, request: Request, current: CurrentUserDep, db: DbDep):
    require("manage_users")(current)
    user = db.query(User).filter(User.id == user_id, User.org_id == current.org_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.role == Role.OWNER.value and current.user.role != Role.OWNER.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners can modify owner accounts")
    if payload.role is not None:
        if payload.role not in [r.value for r in Role]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
        if user.id == current.id and payload.role != user.role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot change own role")
        user.role = payload.role
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        if user.id == current.id and payload.is_active is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate yourself")
        user.is_active = payload.is_active
    audit_log(db, org_id=current.org_id, user_id=current.id, action="user_update",
              resource="user", resource_id=user.id, detail=payload.model_dump(exclude_none=True),
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
