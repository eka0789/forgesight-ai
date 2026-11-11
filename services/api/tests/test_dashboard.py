"""Dashboard aggregation sanity (Module A)."""
from __future__ import annotations


def test_dashboard_summary_shape(client, engineer_headers):
    r = client.get("/api/v1/dashboard/summary", headers=engineer_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {
        "kpis", "production_trend", "defect_distribution", "machine_status",
        "model_metrics", "recent_activity", "ai_system_health", "is_demo_data",
    }
    assert len(body["production_trend"]) == 14
    assert body["ai_system_health"]["llm_mode"] in ("external", "mock-demo")


def test_dashboard_requires_auth(client):
    assert client.get("/api/v1/dashboard/summary").status_code == 401


def test_reports_endpoints(client, engineer_headers):
    for name in ("production", "quality", "maintenance"):
        r = client.get(f"/api/v1/reports/{name}", headers=engineer_headers)
        assert r.status_code == 200
        assert r.json()["report"] == name
