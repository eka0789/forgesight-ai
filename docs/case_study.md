# Case Study — ForgeSight AI

## Business problem

Mid-size manufacturers lose margin to three chronic problems:

1. **Defect escapes** — manual visual inspection is slow, subjective, and
   inconsistent; escaped defects cost 10–100× more downstream.
2. **Unplanned downtime** — reactive maintenance turns small drifts (heat,
   wear, overload) into line-stopping failures.
3. **Tribal knowledge** — SOPs, manuals and specs live in PDFs nobody can
   query; engineers rediscover the same answers every quarter.

## Technical solution

A single industrial platform where each problem is owned by an AI module that
**shares one data spine** (orgs → machines → readings → inspections →
predictions → requests):

- **CV inspection** (OpenCV + CNN/AE): image/video ingestion, annotated defect
  localization with confidence + severity, method transparency.
- **Predictive maintenance** (sklearn/XGBoost): failure probability, RUL,
  health score, failure-mode estimates, persisted predictions feeding the
  dashboard and the agent.
- **Knowledge AI** (hybrid RAG): documents → grounded answers with citations,
  explicit refusal when the knowledge base lacks the answer.
- **Operations agent** (tool-calling state graph): stitches the modules —
  status → predict → incident report → **approval-gated** maintenance request.
- **MLOps**: registry from real artifacts, PSI drift monitoring, Prometheus /
  Grafana, MLflow-compatible experiment tracking.

## System architecture
See [architecture.md](architecture.md) (monolith-first with extractable domain
boundaries; pgvector hybrid retrieval; artifact-driven inference).

## Dataset sources
See [datasets.md](datasets.md) — AI4I 2020 (synthetic mirror w/ documented
thresholds, real-CSV drop-in), C-MAPSS-style RUL trajectories, procedural
defect surfaces.

## Model selection rationale

| Problem | Candidates tried | Selected | Why |
|---|---|---|---|
| Failure classification | LR, RF, HistGB, XGBoost | best-by-val-F1 (RF/HistGB family) | recall-critical; boosted trees won on tabular physics features |
| RUL | RF, HistGB | per-MAE winner | unit-level split to avoid trajectory leakage |
| Defect classification | small CNN vs transfer learning | small CNN on synthetic; ResNet roadmap | CPU-only constraint; transfer learning reserved for real imagery |
| Anomaly detection | AE vs classical stats | AE primary, classical fallback | graceful degradation without torch |
| Clustering | KMeans vs DBSCAN | both, sweep + silhouette | exploratory tool, staged away from decisions |

## Training methodology
Deterministic seeds · leakage-safe splits (scaler-in-pipeline; unit-level for
RUL) · imbalance handled via class weights / scale_pos_weight · selection on
validation, single-touch test · shared feature module train==serve · every
experiment writes params+metrics JSON (MLflow when configured).

## Evaluation results (test splits, honest)

- Failure classifier: **F1 0.917, ROC-AUC 0.981, recall 0.984** (FN=6)
- RUL: **MAE ≈ 12.7 cycles, R² 0.87**
- Defect CNN (14 epochs): **accuracy 0.977** (clean P0.945/R1.0)
- Clustering: best silhouette 0.31 (exploratory)
- Latency: failure inference ~113 ms/1k rows CPU; image inspection pipeline
  typically < 300 ms (classical) incl. annotation

## Performance benchmarks
Prometheus histograms expose HTTP p50/p95 and per-model inference latency;
Grafana dashboard ships preconfigured. Inspection latency is stored per row
(`processing_ms`) and surfaced on the dashboard KPI.

## Deployment strategy
CPU-first Docker Compose (single-node demo/POC) → same images on Kubernetes
with HPA (templates provided). GPU is optional; inference degrades cleanly.
Background tasks (video, ingestion) adopt RQ/Celery without code changes.

## Limitations (read before evaluating)

1. **Synthetic-first datasets**: real-plant retraining is mandatory before any
   operational use; metrics here measure the platform, not a deployed product.
2. **Camera streaming not implemented** — video is file-based by design.
3. **Mock LLM in demo mode** — extractive adapter, clearly labeled; external
   providers activate with keys.
4. Single-node storage/DB in Compose; HA left to managed services.
5. CNN v1 fixed `clean` only after retraining — a transparent example of the
   "never claim performance without running experiments" rule.

## Future improvements

- Transfer learning (ResNet18/YOLO fine-tune) on NEU/MVTec + real factory data
- RUL prediction intervals (quantile ensembles)
- Redis-backed task queue + WS pub/sub fan-out
- LangGraph library adapter + agent eval harness (tool-selection metrics)
- Playwright E2E; SLO alerts in Grafana; automated retraining on drift
