# Architecture — ForgeSight AI

## 1. System overview

```
┌────────────┐   REST/WS    ┌─────────────────────────┐
│  Next.js   │─────────────▶│  FastAPI (services/api) │
│  (apps/web)│              │  ┌────────────────────┐ │
└────────────┘              │  │ api/v1 routers     │ │
                            │  │ auth · machines    │ │
      ┌────────────────────▶│  │ vision · predictions│
      │  JWT (org, role)    │  │ knowledge · agent  │ │
      │                     │  │ mlops · monitoring │ │
      │                     │  └─────────┬──────────┘ │
      │                     │  services: vision / pdm / │
      │                     │  knowledge / agent / mlops│
      │                     └──┬──────┬──────┬────────┘
      ▼                        ▼      ▼      ▼
┌───────────┐  ┌──────────┐ ┌─────────┐ ┌──────────┐
│ PostgreSQL│  │  Redis   │ │  MinIO  │ │ Artifacts│
│ +pgvector │  │ ratelimit│ │ S3 files│ │ ml/...   │
└───────────┘  └──────────┘ └─────────┘ └──────────┘
      │            (MLflow, Prometheus, Grafana via Compose)
      ▼
  Alembic migrations (0001 schema, 0002 pgvector)
```

**Monolith-first with hard module boundaries.** The prompt's five `services/`
(vision, machine-learning, rag, agent) are implemented as **domain packages**
inside one FastAPI app (`app/services/{vision,pdm,knowledge,agent,mlops}`).
Rationale: single deployable for local/edge CPU inference, one auth/RBAC/DB
context, transactional consistency across modules (e.g., agent tool →
prediction → audit log in one session). Each package has no cross-imports of
internals and could be extracted behind HTTP/gRPC without touching routers —
the boundaries are real, just not networked.

## 2. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Auth | JWT HS256 (8h) + bcrypt | stateless, org_id+role embedded; RBAC matrix centralized in `api/deps.py` |
| Tenancy | org_id column on every domain table + query filters | simpler than RLS; cross-tenant tests enforce it |
| Vectors | pgvector on Postgres, JSON+numpy on SQLite | one schema, two dialects via `TypeDecorator`; tests run on SQLite |
| Retrieval | hybrid (BM25-lite + cosine) fused with RRF k=60, light rerank | robust when either signal is weak; no external reranker dependency |
| LLM | provider abstraction (OpenAI/Gemini/**mock-demo**) | deterministic extractive mock = demo mode without pretending external AI |
| Agent | dependency-free state graph, LangGraph-shaped | testable everywhere; nodes are pure state transforms (drop-in adapter possible) |
| Approval | tool-level gate (`needs_approval`) → execution parked `awaiting_approval` | destructive actions never auto-execute; audit trail per tool call |
| Artifacts | `ml/artifacts/` is the single source of truth | training writes joblib/pt + metrics.json; registry & inference read it; baked into image |
| Async work | FastAPI BackgroundTasks + task-function registry | zero extra infra locally; same functions portable to RQ/Celery |
| Degradation | every capability reports its concrete method | `method_used`, `model_version`, `mock-demo`, `rules-only-fallback` — the UI shows what actually ran |

## 3. Data flow examples

**Vision inspection** — `POST /api/v1/vision/inspect` → validate ext/size →
decode → detector router (YOLO if weights, else classical anomaly grid) →
CNN classifier (if artifact) → anomaly score (AE if artifact, else Laplacian
stats) → optional OCR → persist Inspection+Defects+Images → storage save
(original + annotated) → Prometheus counter → WS notify.

**Predictive maintenance** — sensor readings ingested → `GET /machines/{id}/health`
runs trained pipeline (shared feature engineering module with training — no
skew) → per-mode rule estimates blended with model probability → composite
health score → recommendations; `POST /predictions/failure` persists.

**RAG** — upload → background ingest (extract → chunk → embed → index) →
`POST /knowledge/chat` → hybrid search → sanitized context → LLM (or mock) →
citations verified → conversation persisted.

**Agent** — `POST /agent/chat` → planner (LLM JSON or rules) → sequential tool
execution (each logged w/ duration) → approval gate for sensitive tools →
LLM synthesis or transparent rule summary → execution + messages persisted.

## 4. Observability

- `/metrics` (Prometheus): HTTP latency histogram (p50/p95 via Grafana),
  inference latency per model, inspection/prediction counters, WS gauge.
- `/api/v1/monitoring/health` — DB/Redis/storage/artifacts/provider status.
- `/api/v1/monitoring/drift` — PSI per feature vs training reference stats
  (stored inside the model bundle at train time).
- Structured JSON logs in production mode.

## 5. Testing strategy

pytest (49 tests): auth flows, RBAC matrix, cross-tenant isolation, file-type
validation, vision pipeline (incl. real annotated output + video async), PDM
with real artifacts, RAG grounding + refusal + injection resistance, agent
tool execution + approval RBAC, registry/drift, Prometheus scrape. Frontend
verified via type-checked production build; E2E via Playwright is roadmap.
External AI providers are mocked by construction (provider fallback), so the
suite runs offline.
