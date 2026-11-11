"""ForgeSight AI — FastAPI application entrypoint."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import APP_INFO, REQUEST_LATENCY
from app.core.rate_limit import limiter

APP_INFO.labels(version=__version__, env=settings.env).set(1)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = request.scope.get("route").path if request.scope.get("route") else request.url.path
            REQUEST_LATENCY.labels(
                method=request.method, endpoint=path, status=str(status_code)
            ).observe(elapsed)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.rate_limit_enabled and request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            if not limiter.hit(f"api:{ip}", settings.rate_limit_per_minute):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger(__name__)
    setup_logging()

    if settings.env == "production" and settings.secret_key == "change-me-in-production":
        # Fail fast — an insecure JWT secret in production is a hard error.
        raise RuntimeError(
            "SECRET_KEY is still the default value — refusing to start in production. "
            "Set a strong SECRET_KEY (python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )

    # Dev convenience: create tables without alembic (production uses migrations).
    if settings.env == "development":
        from app.db.base import Base
        from app.db.session import engine

        Base.metadata.create_all(bind=engine)

    # Warm model artifacts (real inference availability)
    try:
        from app.services.pdm import inference as pdm

        pdm.artifacts.load()
    except Exception as exc:  # pragma: no cover
        import logging

        logging.getLogger(__name__).warning("artifact warmup failed: %s", exc)

    # Registry + demo seed (idempotent)
    if settings.seed_demo:
        from app.seed import seed_demo

        seed_demo()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Industrial AI Intelligence Platform: Computer Vision Inspection, "
            "Predictive Maintenance, RAG Knowledge AI, Operations Agent, MLOps."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.include_router(api_router)

    @app.get("/health", tags=["ops"])
    def root_health():
        return {"status": "ok", "app": settings.app_name, "version": __version__}

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def prometheus_metrics():
        from fastapi.responses import Response

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()
