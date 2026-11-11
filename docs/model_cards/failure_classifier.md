# Model Card — Machine Failure Classifier

**Version**: v1.0.0-20261110 · **Task**: tabular binary classification
(machine failure within operating conditions) · **Framework**: scikit-learn /
XGBoost

## Intended use
Estimate failure probability for industrial machines from AI4I-style sensor
readings (air/process temperature, rotational speed, torque, tool wear,
vibration) to prioritize inspections and maintenance. Served at
`POST /api/v1/predictions/failure` and `GET /machines/{id}/health`.

## Training data
`ml/datasets/ai4i_synthetic.csv` (SYNTHETIC mirror of AI4I 2020; see
docs/datasets.md). Split 60/20/20 stratified, leakage-safe (scaler inside
pipeline fitted on train only).

## Features
6 raw channels + 4 engineered (`temp_delta`, `power_w`,
`wear_torque_product`, `speed_torque_ratio`) — shared module
`app/services/pdm/features.py` used identically in training and inference.

## Candidates compared (validation F1)
LogisticRegression (balanced) · RandomForest (balanced_subsample) ·
HistGradientBoosting · XGBoost (scale_pos_weight) — best-by-val-F1 refit on
train+val, evaluated once on test.

## Measured results (test, honest)
- accuracy / precision / recall / **F1** = 0.967 / 0.859 / 0.984 / **0.917**
- ROC-AUC 0.981 · PR-AUC 0.898
- Confusion matrix: FN = 6, FP = 60 (recall prioritized for safety)
- Inference latency: ~113 ms / 1k rows (CPU)
- Full JSON: `ml/artifacts/pdm/metrics.json` → key `failure`

## Serving & fallback
If the artifact is missing the API returns `model_version:
rules-only-fallback` with rule-based estimates and an explicit note — it
never fabricates model output. Per-failure-mode probabilities (TWF/HDF/PWF/OSF)
are documented AI4I-threshold heuristics blended (30%) with the model's
overall probability; they are labeled as such in responses.

## Limitations & ethical notes
- Trained on synthetic data — do not deploy to a real factory without
  retraining on that plant's data and validating with domain engineers.
- Class balance and thresholds differ from the real AI4I dataset.
- Predictions are decision support, not autonomous maintenance authority;
  sensitive actions (maintenance requests) require human approval by design.
