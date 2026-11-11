from fastapi import APIRouter

from app.api.v1 import (
    agent,
    auth,
    dashboard,
    knowledge,
    machines,
    mlops,
    monitoring,
    predictions,
    reports,
    users,
    vision,
)
from app.api.v1.mlops import datasets_router, experiments_router
from app.api.v1.predictions import requests_router
from app.api.v1.ws import ws_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(machines.router)
api_router.include_router(vision.router)
api_router.include_router(predictions.router)
api_router.include_router(requests_router)
api_router.include_router(knowledge.router)
api_router.include_router(agent.router)
api_router.include_router(mlops.router)
api_router.include_router(experiments_router)
api_router.include_router(datasets_router)
api_router.include_router(monitoring.router)
api_router.include_router(reports.router)
# WebSocket live events (was imported but never mounted — found by lint audit)
api_router.include_router(ws_router)
