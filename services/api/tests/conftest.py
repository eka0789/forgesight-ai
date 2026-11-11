"""Pytest fixtures — isolated SQLite DB, temp storage, real artifacts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Environment MUST be configured before importing app modules (settings are
# read at import time).
_TMP = tempfile.mkdtemp(prefix="fsg_test_")
os.environ["ENV"] = "development"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP) / 'test_forgesight.db'}"
os.environ["STORAGE_DIR"] = str(Path(_TMP) / "storage")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["SEED_DEMO"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def client(engine):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:  # runs lifespan (artifact warmup, no seed)
        yield c


@pytest.fixture()
def db(engine):
    from app.db.session import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def org1(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "owner1@example.com", "password": "Password123!",
        "full_name": "Owner One", "organization_name": "Test Org One",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="session")
def org2(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "owner2@example.com", "password": "Password123!",
        "full_name": "Owner Two", "organization_name": "Test Org Two",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="session")
def headers1(org1):
    return {"Authorization": f"Bearer {org1['access_token']}"}


@pytest.fixture(scope="session")
def headers2(org2):
    return {"Authorization": f"Bearer {org2['access_token']}"}


@pytest.fixture(scope="session")
def engineer_headers(client, org1):
    token = org1["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/v1/users", headers=h, json={
        "email": "engineer@example.com", "password": "Password123!",
        "full_name": "Test Engineer", "role": "engineer",
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", data={"username": "engineer@example.com", "password": "Password123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def viewer_headers(client, org1):
    token = org1["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/v1/users", headers=h, json={
        "email": "viewer@example.com", "password": "Password123!",
        "full_name": "Test Viewer", "role": "viewer",
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", data={"username": "viewer@example.com", "password": "Password123!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
