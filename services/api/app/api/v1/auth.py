from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUserDep, DbDep
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginOut, RegisterIn, TokenOut, UserOut
from app.services.audit import audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


def _reissue(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.org_id, user.role),
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.post("/register", response_model=LoginOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: DbDep):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    base_slug = payload.organization_name.lower().replace(" ", "-")[:60] or "org"
    slug = base_slug
    suffix = 0
    while db.query(Organization).filter(Organization.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    db.flush()

    user = User(
        org_id=org.id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    audit_log(db, org_id=org.id, user_id=user.id, action="register",
              resource="user", resource_id=user.id, ip=request.client.host if request.client else None)
    db.commit()

    token = _reissue(user)
    return LoginOut(
        **token.model_dump(),
        user=UserOut.model_validate(user),
        organization={"id": org.id, "name": org.name, "slug": org.slug, "is_demo": org.is_demo},
    )


@router.post("/login", response_model=LoginOut)
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: DbDep = None):
    ip = request.client.host if (request and request.client) else "unknown"
    if not limiter.hit(f"login:{ip}", settings.rate_limit_login_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")

    user = db.query(User).filter(User.email == (form.username or "").lower()).first()
    if not user or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    user.last_login_at = datetime.now(timezone.utc)
    audit_log(db, org_id=user.org_id, user_id=user.id, action="login",
              resource="user", resource_id=user.id, ip=ip)
    db.commit()
    db.refresh(user)

    token = _reissue(user)
    org = db.get(Organization, user.org_id)
    return LoginOut(
        **token.model_dump(),
        user=UserOut.model_validate(user),
        organization={"id": org.id, "name": org.name, "slug": org.slug, "is_demo": org.is_demo},
    )


@router.get("/me", response_model=LoginOut)
def me(current: CurrentUserDep, db: DbDep):
    org = db.get(Organization, current.org_id)
    token = _reissue(current.user)
    return LoginOut(
        **token.model_dump(),
        user=UserOut.model_validate(current.user),
        organization={"id": org.id, "name": org.name, "slug": org.slug, "is_demo": org.is_demo},
    )
