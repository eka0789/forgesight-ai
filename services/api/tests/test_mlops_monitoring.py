"""MLOps registry + monitoring endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.mlops.registry import register_all


def test_registry_registers_trained_models(client, db, engineer_headers):
    result = register_all(db)
    assert result["registered"], "expected at least one registered model from artifacts"

    r = client.get("/api/v1/models", headers=engineer_headers)
    assert r.status_code == 200
    names = {m["name"] for m in r.json()["items"]}
    assert "failure_classifier" in names
    failure = next(m for m in r.json()["items"] if m["name"] == "failure_classifier")
    assert any(v["status"] == "production" for v in failure["versions"])


def test_model_metrics_endpoint(client, engineer_headers):
    r = client.get("/api/v1/models", headers=engineer_headers)
    mid = r.json()["items"][0]["id"]
    r2 = client.get(f"/api/v1/models/{mid}/metrics", headers=engineer_headers)
    assert r2.status_code == 200
    assert "versions" in r2.json()


def test_experiments_and_datasets_endpoints(client, engineer_headers):
    assert client.get("/api/v1/experiments", headers=engineer_headers).status_code == 200
    assert client.get("/api/v1/datasets", headers=engineer_headers).status_code == 200


def test_monitoring_health_public(client):
    r = client.get("/api/v1/monitoring/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "up"
    assert body["version"]


def test_monitoring_metrics_requires_auth(client):
    assert client.get("/api/v1/monitoring/metrics").status_code == 401


def test_drift_report_with_data(client, db, engineer_headers):
    from app.models.machine import Machine, SensorReading

    machine = db.query(Machine).filter(Machine.org_id == 1).first()
    if machine is None:
        machine = Machine(org_id=1, code="DRIFT-1", name="Drift Machine")
        db.add(machine)
        db.flush()

    import numpy as np

    rng = np.random.default_rng(7)
    now = datetime.now(timezone.utc)
    for j in range(40):
        db.add(SensorReading(
            machine_id=machine.id, ts=now - timedelta(hours=j),
            air_temperature=float(rng.normal(300, 2)),
            process_temperature=float(rng.normal(310, 2)),
            rotational_speed=float(rng.normal(1500, 120)),
            torque=float(rng.normal(40, 10)),
            tool_wear=float(rng.normal(100, 30)),
            vibration=float(rng.normal(1.5, 0.5)),
        ))
    db.commit()

    r = client.get("/api/v1/monitoring/drift?days=7", headers=engineer_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert "psi_per_feature" in body
    assert body["verdict"] in ("stable", "moderate drift", "significant drift")


def test_prometheus_metrics_scrape(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"fsg_http_request_latency" in r.content
