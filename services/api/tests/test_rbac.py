"""RBAC matrix + cross-tenant isolation."""
from __future__ import annotations


def test_viewer_cannot_create_machine(client, viewer_headers):
    r = client.post("/api/v1/machines", headers=viewer_headers, json={
        "code": "V1", "name": "Viewer Machine",
    })
    assert r.status_code == 403


def test_viewer_can_read_machines(client, viewer_headers):
    r = client.get("/api/v1/machines", headers=viewer_headers)
    assert r.status_code == 200


def test_operator_role_restricted(client, org1):
    h = {"Authorization": f"Bearer {org1['access_token']}"}
    r = client.post("/api/v1/users", headers=h, json={
        "email": "operator@example.com", "password": "Password123!",
        "full_name": "Op", "role": "operator",
    })
    assert r.status_code == 201
    r = client.post("/api/v1/auth/login", data={"username": "operator@example.com", "password": "Password123!"})
    oh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # operator can run inspections (after machine exists) but not manage users
    assert client.get("/api/v1/users", headers=oh).status_code == 403


def test_cross_tenant_machine_hidden(client, org1, org2, headers1, headers2):
    h1 = headers1
    r = client.post("/api/v1/machines", headers=h1, json={"code": "X-TENANT", "name": "Org1 Only"})
    assert r.status_code == 201
    machine_id = r.json()["id"]

    r2 = client.get(f"/api/v1/machines/{machine_id}", headers=headers2)
    assert r2.status_code == 404

    # org2 cannot ingest readings into org1's machine
    r3 = client.post(f"/api/v1/machines/{machine_id}/readings", headers=headers2, json={
        "air_temperature": 300, "process_temperature": 310, "rotational_speed": 1500,
        "torque": 40, "tool_wear": 10,
    })
    assert r3.status_code == 404


def test_invalid_role_rejected(client, org1):
    h = {"Authorization": f"Bearer {org1['access_token']}"}
    r = client.post("/api/v1/users", headers=h, json={
        "email": "badrole@example.com", "password": "Password123!",
        "full_name": "Bad", "role": "superadmin",
    })
    assert r.status_code == 400


def test_cannot_change_own_role(client, org1):
    h = {"Authorization": f"Bearer {org1['access_token']}"}
    uid = org1["user"]["id"]
    r = client.patch(f"/api/v1/users/{uid}", headers=h, json={"role": "viewer"})
    assert r.status_code == 400
