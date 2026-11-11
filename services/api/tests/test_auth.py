"""Authentication flows and security behaviors."""
from __future__ import annotations


def test_register_creates_owner(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "authowner@example.com", "password": "Password123!",
        "full_name": "Auth Owner", "organization_name": "Auth Test Org",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "owner"
    assert body["access_token"]
    assert body["organization"]["name"] == "Auth Test Org"


def test_register_duplicate_email_conflict(client, org1):
    r = client.post("/api/v1/auth/register", json={
        "email": "owner1@example.com", "password": "Password123!",
        "full_name": "Dup", "organization_name": "Another Org",
    })
    assert r.status_code == 409


def test_register_short_password_422(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "short@example.com", "password": "short",
        "full_name": "S", "organization_name": "Org",
    })
    assert r.status_code == 422


def test_login_success_and_me(client, org1):
    r = client.post("/api/v1/auth/login", data={"username": "owner1@example.com", "password": "Password123!"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "owner1@example.com"


def test_login_wrong_password_401(client, org1):
    r = client.post("/api/v1/auth/login", data={"username": "owner1@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_tampered_token_401(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401
