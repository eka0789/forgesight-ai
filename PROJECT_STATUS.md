# PROJECT STATUS — ForgeSight AI

> Build log maintained across sessions. Last updated: 2026-11-12.

## 🚀 GitHub & CI (2026-11-12)

- Repo: **https://github.com/eka0789/forgesight-ai** (public, `main`)
- Commits: `4387fa9` full build → `3edb499` CI lint fix (unused logger) →
  `ecc0fdc` CI pytest fix (`python -m pytest`) → `882a4d3` torch-optional fix
- **CI: all 4 jobs green** — `ml-training` ✓ `web` ✓ `backend` ✓ `docker-build` ✓
- CI caught 3 real issues that local runs missed:
  1. `F841` unused logger (edit made after last local lint run)
  2. bare `pytest` doesn't add CWD to `sys.path` → `python -m pytest`
  3. **module-level torch imports broke the no-torch contract** — `cnn_model`/
     `ae_model` now define model classes only when torch exists; verified
     locally by importing `app.main` with torch blocked (degrades to classical CV)

## 🧹 Full audit pass (2026-11-12) — semua temuan diperbaiki

### Findings & fixes
| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | **WS router imported but never mounted** → `/api/v1/ws` 404 (ditemukan ruff F401) | HIGH | `api_router.include_router(ws_router)` + 3 regression tests (auth-gate 4401, tampered token, ping/pong) |
| 2 | Vision detector rebuilt per request → YOLO weights would reload on every inspect | HIGH | lazy singleton `_get_detector()` |
| 3 | Agent had declared-but-unenforced tool timeout | MEDIUM | ThreadPool-enforced `TOOL_TIMEOUT_SECONDS=30` + auto-retry (2 attempts) + rollback between attempts; failures stay structured tool-logs |
| 4 | Compose `alembic && seed || true && uvicorn` precedence bug — migration failure could still start the server | MEDIUM | explicit `{ … }` grouping + `exec uvicorn` |
| 5 | `env_file: .env` mandatory → `docker compose config` fails on fresh clone | MEDIUM | `required: false` |
| 6 | `redis` package missing → compose rate limiting silently fell back to memory | MEDIUM | added to requirements |
| 7 | Production could boot with default `SECRET_KEY` | HIGH | lifespan hard-fails in `env=production` |
| 8 | `seed.py` used randomized `hash()` → non-deterministic demo images across processes | LOW | `zlib.crc32` |
| 9 | CI: backend tests assumed artifacts that the job never built; lint was `--exit-zero` | MEDIUM | backend job now `needs: ml-training` + downloads artifact; ruff must be clean |
| 10 | WS notify only fired for unlinked inspections | LOW | notify always |
| 11 | ruff: 73 findings (unused imports, import order); eslint: 7 warnings; stray debug DBs | LOW | all cleaned to **zero** |
| 12 | ml/ + scripts/ lint: 27 findings (unused vars, import order, blind except) | LOW | cleaned to **zero** |
| 13 | `mlflow` service double-installed psycopg2 at boot; web Dockerfile healthcheck via wget OK | LOW | left (documented); verified compose-valid |

### Post-audit verification (all green)
- `ruff check app tests ml scripts` → **All checks passed** (0 findings across the repo)
- `pytest` → **52/52 passed** (49 + 3 new WS regression tests)
- `npx eslint app components lib` → **0 problems**
- `npm run build` → **succeeded, no errors** (15 routes)
- `docker compose config` → **valid**
- All CI/monitoring YAML + dashboard JSON → **parsed OK**
- Live boot smoke (seed + login + dashboard + 48 OpenAPI paths) → **OK**
- **Training pipeline re-run post-lint** (proves scripts still execute): failure F1 0.9171 (deterministic reproduction), RUL R² 0.8707, KMeans silhouette 0.3067
- **CNN + AE retrained after lint fixes** (exit 0): CNN accuracy/F1 **0.9771** reproduced; AE defect detection rate **1.0** @ clean FPR **0.0125** — artifacts refreshed 2026-11-12

## 🔬 Live verification (2026-11-11, original build)

| Check | Result |
|---|---|
| Alembic migration chain on SQLite | 2 revisions → 23 tables ✓ |
| Alembic migration chain on **PostgreSQL (docker pgvector/pg16)** | ✓ incl. `CREATE EXTENSION vector`, column → `vector(384)`, ivfflat index present |
| Live API smoke (uvicorn + SEED_DEMO) | login ✓ dashboard KPIs ✓ machine health via **trained artifact** (`is_prediction_available=true`) ✓ |
| RAG grounded chat (live) | mock-demo labeled ✓ real citations ✓ |
| Agent tool run (live) | `get_machine_status` executed, audit logged ✓ |
| Model registry (live) | failure_classifier/rul = **production**; cnn/ae/clustering = staging ✓ |
| Drift report (live) | PSI computed vs training reference ✓ |
| Prometheus metrics endpoint | `fsg_*` series exposed ✓ |

## ✅ Completed (Phase 1–8, single-session full build)

### Phase 1 — Foundation
- Monorepo scaffold: `apps/web`, `services/api`, `ml/`, `infrastructure/`, `scripts/`
- FastAPI app factory, pydantic-settings config, JSON logging, rate limiting
  (Redis w/ in-memory fallback), Prometheus middleware
- 20+ SQLAlchemy 2.0 tables with FKs/indexes; Alembic migrations
  (`0001_initial_schema` + `0002_pgvector` for Postgres)
- JWT auth (bcrypt), RBAC matrix (owner/admin/engineer/operator/viewer),
  organization tenant isolation, audit logging

### Phase 2 — Data Science & ML
- AI4I-style **synthetic dataset generator** (documented thresholds; auto-uses
  real CSV when dropped in) — 10,000 rows, ~18% failure rate
- **Failure classifier**: LR / RF / HistGB / XGBoost compared; best selected on
  validation F1, refit on train+val, evaluated on untouched test split
  → **test F1 0.917, ROC-AUC 0.981, recall 0.984**
- **RUL regressor**: synthetic C-MAPSS-style degradation (60k rows); RF vs HistGB
  → **test MAE ~12.7 cycles, R² 0.87**
- **Clustering**: KMeans k-sweep (silhouette 0.31 best) + DBSCAN eps sweep
- MLflow-compatible tracking hooks (active when `MLFLOW_TRACKING_URI` set)

### Phase 3 — Deep Learning & CV
- OpenCV preprocessing (CLAHE, denoise), classical anomaly grid detector
  (median/MAD z-score, severity mapping) — always available, real method
- **Defect CNN** (PyTorch, shared arch module train+serve) trained on procedural
  synthetic surfaces (clean/scratch/stain/dent), 14 epochs, 480×4 images
  → **test accuracy 0.977, F1-weighted 0.977** (v1 at 6 epochs was honestly 0.73;
  retrain with more data/epochs fixed the `clean` class)
- **Anomaly autoencoder**: threshold = clean mean+2σ; detection rates recorded
- YOLO integration path (env `VISION_YOLO_WEIGHTS`), OCR (tesseract guarded)
- Video: frame-sampled async pipeline via background tasks

### Phase 4 — Generative AI & RAG
- LLM provider abstraction: OpenAI / Gemini / **mock-demo** (deterministic
  extractive, labeled) — switchable via env, zero business-logic changes
- Embedding providers: OpenAI / sentence-transformers / **local hashing** (384-d)
- Ingestion pipeline (PDF/TXT/DOCX/CSV) → chunking w/ page tracking → embeddings
  → pgvector (Postgres) or JSON+numpy (SQLite)
- **Hybrid retrieval**: BM25-lite keyword + vector cosine, RRF fusion, rerank
- Grounded chat: citations only from real chunks, refusal when no context,
  prompt-injection sanitization (tested)

### Phase 5 — AI Agent
- LangGraph-style state graph (dependency-free nodes: intent→plan→tools→validate→respond)
- 8 Pydantic-validated tools; **create_maintenance_request gated behind human approval**
- Conversation memory, tool logs w/ durations, iteration cap (8), per-tool timeout
- LLM planner when key present, rule-based planner otherwise (labeled)

### Phase 6 — Frontend
- Next.js 16 + TypeScript + Tailwind 4 (industrial dark/light theme)
- 11 screens: login/register, dashboard, vision workspace, maintenance,
  knowledge (docs+chat w/ citations), agent workspace (+executions+tools),
  ML lab (experiments + browser RL sim), model registry (+detail), monitoring
  (health+counters+drift), reports (3 types), settings (org+users)
- Loading/empty/error states, demo-data banner, RBAC-aware controls

### Phase 7 — MLOps
- Model registry seeded from artifacts (production/staging statuses)
- PSI drift detection endpoint vs training reference stats
- Prometheus metrics (latency histograms, counters) + Grafana dashboard JSON

### Phase 8 — Production readiness
- **49/49 pytest tests green** (auth, RBAC, tenants, file validation, vision
  pipeline, RAG safeguards, agent approval, drift, prometheus scrape)
- Docker images (non-root, healthchecks) + full Compose stack
  (pg+pgvector, redis, minio, api, web, mlflow, prometheus, grafana)
- GitHub Actions CI (tests, ML training w/ artifact assertions, web build, image builds)
- K8s templates + HPA; docs (architecture, datasets, model cards, case study)

## 🧪 Measured results (real runs, this repo)

| Model | Metric | Value (test) |
|---|---|---|
| failure_classifier | F1 / ROC-AUC / recall | 0.917 / 0.981 / 0.984 |
| rul_regressor | MAE / R² | ~12.7 cycles / 0.87 |
| clustering (KMeans best k) | silhouette | 0.31 |
| defect_cnn (14 epochs, 480×4 images) | accuracy / F1-w | **0.977 / 0.977** (clean: P 0.945 / R 1.0) |
| anomaly_ae | defect detection rate / clean FPR | see `ml/artifacts/vision/ae_metrics.json` |

## ⚠️ Known limitations (honest)

1. **Synthetic imagery**: the CNN was trained on procedurally generated defect
   images (documented) — real production imagery requires transfer learning on
   factory-specific data (NEU/MVTec loaders scaffolded in docs).
2. Datasets are **synthetic mirrors** of AI4I 2020 / C-MAPSS schemas — drop real
   CSVs into `ml/datasets/` (`ai4i_real.csv`, `cmapps_real.csv`) and rerun.
3. **Camera streaming is not implemented** — no real-time claims are made.
4. Background tasks are in-process (FastAPI BackgroundTasks); a Redis-backed
   worker (RQ/Celery) is the documented next step for horizontal scale.
5. WebSocket events are in-memory per process; Redis pub/sub adapter needed
   for multi-replica fan-out.
6. Single Postgres instance in Compose (no HA); production needs managed DB.

## 🔜 Remaining roadmap

- [x] CNN retrain with more data/epochs → 0.977 accuracy (done)
- [ ] RQ/Celery worker adoption of `app/workers/tasks.py` (same task functions)
- [ ] Redis pub/sub for cross-replica WS events
- [ ] LangGraph library adapter (graph nodes are already isolated)
- [ ] Real YOLO fine-tune on NEU surface-defect dataset (loader scaffolded)
- [ ] Playwright E2E suite for the web UI
- [ ] Alembic migration verification against live pgvector container (below)
