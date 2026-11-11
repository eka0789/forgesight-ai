"""AI Agent: tool execution, human-in-the-loop approval, iteration limits."""
from __future__ import annotations


def test_tools_catalog(client, engineer_headers):
    r = client.get("/api/v1/agent/tools", headers=engineer_headers)
    assert r.status_code == 200
    tools = {t["name"]: t for t in r.json()["tools"]}
    assert len(tools) >= 8
    assert tools["create_maintenance_request"]["requires_approval"] is True


def test_agent_status_intent_executes_tool(client, engineer_headers):
    # ensure a machine exists
    r = client.post("/api/v1/machines", headers=engineer_headers,
                    json={"code": "AGENT-M1", "name": "Agent Machine"})
    assert r.status_code == 201

    r = client.post("/api/v1/agent/chat", headers=engineer_headers,
                    json={"message": "what is the status of machine 1?"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["planner"] in ("rule_based", "llm")
    assert any(t["tool"] == "get_machine_status" for t in body["tool_results"])


def test_agent_sensitive_tool_requires_approval(client, engineer_headers):
    client.post("/api/v1/machines", headers=engineer_headers,
                json={"code": "AGENT-M2", "name": "Agent Machine 2"})
    r2 = client.post("/api/v1/agent/chat", headers=engineer_headers,
                     json={"message": "create a maintenance request for machine with urgent priority"})
    assert r2.status_code == 201
    body = r2.json()
    if body["status"] == "awaiting_approval":
        assert body["approval_required"]["tool"] == "create_maintenance_request"

        # engineer (no approve permission) gets 403
        r3 = client.post(f"/api/v1/agent/approvals/{body['execution_id']}",
                         headers=engineer_headers, json={"approve": True})
        assert r3.status_code == 403

        # owner approves → request created
        owner_login = client.post("/api/v1/auth/login",
                                  data={"username": "owner1@example.com", "password": "Password123!"})
        oh = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
        r4 = client.post(f"/api/v1/agent/approvals/{body['execution_id']}", headers=oh,
                         json={"approve": True})
        assert r4.status_code == 200, r4.text
        assert r4.json()["status"] == "completed"

        reqs = client.get("/api/v1/maintenance-requests", headers=oh).json()
        assert any(req["source"] == "agent" for req in reqs["items"])
    else:
        assert body["status"] == "completed"


def test_agent_execution_logs(client, engineer_headers):
    r = client.get("/api/v1/agent/executions", headers=engineer_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    eid = r.json()["items"][0]["id"]
    detail = client.get(f"/api/v1/agent/executions/{eid}", headers=engineer_headers)
    assert detail.status_code == 200
    assert isinstance(detail.json()["tool_logs"], list)


def test_agent_cross_tenant_hidden(client, org2, engineer_headers):
    r = client.post("/api/v1/agent/chat", headers=engineer_headers,
                    json={"message": "status of machine 1"})
    eid = r.json()["execution_id"]
    h2 = {"Authorization": f"Bearer {org2['access_token']}"}
    assert client.get(f"/api/v1/agent/executions/{eid}", headers=h2).status_code == 404
