"""Machines + predictive maintenance (real artifacts when present)."""
from __future__ import annotations

READING = {
    "air_temperature": 298.0,
    "process_temperature": 305.5,
    "rotational_speed": 1550.0,
    "torque": 42.0,
    "tool_wear": 120.0,
    "vibration": 1.6,
}


def _create_machine(client, headers, code="PDM-1"):
    r = client.post("/api/v1/machines", headers=headers, json={"code": code, "name": "Test Machine"})
    assert r.status_code == 201, r.text
    return r.json()


def test_machine_crud_and_readings(client, headers1):
    m = _create_machine(client, headers1, "PDM-CRUD")
    mid = m["id"]

    r = client.post(f"/api/v1/machines/{mid}/readings", headers=headers1, json=READING)
    assert r.status_code == 201

    r = client.get(f"/api/v1/machines/{mid}/readings", headers=headers1)
    assert r.status_code == 200 and r.json()["total"] >= 1

    r = client.patch(f"/api/v1/machines/{mid}", headers=headers1, json={"status": "warning"})
    assert r.status_code == 200 and r.json()["status"] == "warning"

    r = client.delete(f"/api/v1/machines/{mid}", headers=headers1)
    assert r.status_code == 204
    # soft delete: machine no longer listed but still exists for audit
    r = client.get("/api/v1/machines", headers=headers1)
    assert all(item["code"] != "PDM-CRUD" for item in r.json()["items"])


def test_health_uses_trained_model(client, headers1):
    """With real artifacts present, health returns model-backed prediction."""
    m = _create_machine(client, headers1, "PDM-HEALTH")
    mid = m["id"]
    for i in range(3):
        r = client.post(f"/api/v1/machines/{mid}/readings", headers=headers1, json=READING)
        assert r.status_code == 201

    r = client.get(f"/api/v1/machines/{mid}/health", headers=headers1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0.0 <= body["failure_probability"] <= 1.0
    assert body["risk_level"] in ("low", "medium", "high", "critical")
    assert isinstance(body["health_score"], (int, float))
    # artifacts were trained in this repo; rules-only fallback should not appear
    assert body["model_version"] != "rules-only-fallback"


def test_health_without_readings_notes_missing(client, headers1):
    m = _create_machine(client, headers1, "PDM-EMPTY")
    r = client.get(f"/api/v1/machines/{m['id']}/health", headers=headers1)
    assert r.status_code == 200
    assert r.json()["note"] is not None


def test_prediction_endpoint_persists(client, headers1):
    m = _create_machine(client, headers1, "PDM-PRED")
    client.post(f"/api/v1/machines/{m['id']}/readings", headers=headers1, json=READING)
    r = client.post("/api/v1/predictions/failure", headers=headers1, json={"machine_id": m["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["failure_probability"] >= 0.0
    assert r.json()["model_version"]

    r2 = client.get("/api/v1/predictions", headers=headers1)
    assert r2.status_code == 200 and r2.json()["total"] >= 1


def test_prediction_requires_sensor_data(client, headers1):
    m = _create_machine(client, headers1, "PDM-NOREAD")
    r = client.post("/api/v1/predictions/failure", headers=headers1, json={"machine_id": m["id"]})
    assert r.status_code == 409


def test_rul_endpoint(client, headers1):
    m = _create_machine(client, headers1, "PDM-RUL")
    client.post(f"/api/v1/machines/{m['id']}/readings", headers=headers1, json=READING)
    r = client.post("/api/v1/predictions/rul", headers=headers1,
                    json={"machine_id": m["id"], "cycles_elapsed": 50})
    assert r.status_code == 201, r.text
    assert r.json()["rul_hours"] >= 0


def test_prediction_permission(client, viewer_headers):
    r = client.post("/api/v1/predictions/failure", headers=viewer_headers, json={"machine_id": 1})
    assert r.status_code == 403
