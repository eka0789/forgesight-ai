# API — ForgeSight AI

Interactive docs: **http://localhost:8000/docs** (OpenAPI 3.1, exported to
`shared/contracts/openapi.json` via `scripts/export_openapi.py`).

## Conventions
- Versioned prefix `/api/v1` · JWT bearer auth · JSON errors
  `{detail}` · pagination `{items,total,page,page_size,pages}` · RBAC matrix in
  `app/api/deps.py`.

## Endpoint map

### Auth
| Method | Path | Perm | Notes |
|---|---|---|---|
| POST | /api/v1/auth/register | public | creates org + owner; rate-limited |
| POST | /api/v1/auth/login | public | OAuth2 form; per-IP limiter |
| GET | /api/v1/auth/me | user | returns user + org |

### Users (manage_users)
GET/POST `/users` · PATCH `/users/{id}` (cannot change own role)

### Dashboard / Reports
GET `/dashboard/summary` · GET `/reports/{production,quality,maintenance}`

### Machines (read; manage_machines for writes)
GET/POST `/machines` · GET/PATCH/DELETE `/machines/{id}` (soft delete) ·
POST/GET `/machines/{id}/readings` (AI4I-style payload) ·
GET `/machines/{id}/health` (real inference; rules-fallback labeled) ·
GET `/machines/{id}/predictions`

### Vision (run_inspection)
POST `/vision/inspect` — image (sync, ≤10 MB; ext whitelist)
POST `/vision/video` — video (202 async, ≤150 MB)
GET `/vision/inspections` (+filters) · GET `/vision/inspections/{id}` ·
GET `/vision/inspections/{id}/image|annotated` (binary)

### Predictions (create_prediction)
POST `/predictions/failure` — `{machine_id}` or `{reading}`
POST `/predictions/rul` — optional `cycles_elapsed`
GET `/predictions`

### Maintenance requests (manage_requests / approve_requests)
GET/POST `/maintenance-requests` · POST `/{id}/approve|reject` ·
PATCH `/{id}/status`

### Knowledge (manage_documents for writes, read for search/chat)
POST `/knowledge/upload` (202; async ingest) · GET `/knowledge/documents` ·
DELETE `/knowledge/documents/{id}` · POST `/knowledge/search` (hybrid) ·
POST `/knowledge/chat` (grounded + citations) · GET `/knowledge/conversations`
· GET `/knowledge/conversations/{id}/messages`

### Agent (use_agent)
POST `/agent/chat` · GET `/agent/executions[/{id}]` ·
POST `/agent/approvals/{execution_id}` (approve_requests) · GET `/agent/tools`

### MLOps
GET `/models[/{id}[/metrics]]` · GET `/experiments` · GET `/datasets`

### Monitoring
GET `/monitoring/health` (public) · GET `/monitoring/metrics` ·
GET `/monitoring/drift?days=7` · `/metrics` (Prometheus, internal) ·
`/health` (root, public)

### WebSocket
`/ws?token=JWT` — org-scoped events (`inspection_completed`, …), ping/pong.

## Example: failure prediction

```bash
curl -X POST http://localhost:8000/api/v1/predictions/failure \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
# → {"failure_probability": 0.42, "risk_level": "medium",
#    "predicted_modes": {"TWF": 0.11, "HDF": 0.31, ...},
#    "model_version": "v1.0.0-20261110", "recommendations": [...]}
```
