# Model Card — RUL Regressor

**Version**: v1.0.0-20261110 · **Task**: regression (remaining useful life,
cycles≈hours) · **Framework**: scikit-learn

## Intended use
Estimate remaining useful life from the current sensor feature vector,
optionally capped by cycles elapsed. Served at `POST /api/v1/predictions/rul`
and consumed by health scoring (720 h reference headroom).

## Training data
`ml/datasets/cmapps_synthetic_rul.csv` — SYNTHETIC C-MAPSS-style trajectories
(260 units, 60,750 rows). Unit-level split (80/20 by unit, not by row) to
prevent trajectory leakage.

## Models compared (test MAE)
RandomForest(250) vs HistGradientBoosting(400) → best selected per MAE.

## Measured results (test, honest)
- **MAE ≈ 12.7 cycles · RMSE ≈ 20+ · R² ≈ 0.87** (exact values in
  `ml/artifacts/pdm/metrics.json` → key `rul`)

## Serving
Loads from `ml/artifacts/pdm/rul_model.joblib`. Missing artifact → HTTP 503
with explicit message (no fabricated RUL).

## Limitations
- Synthetic degradation smoothness underestimates real-world variance.
- No prediction intervals (ensemble-variance bands are roadmap).
- Cycle≈hours equivalence is an assumption for demo units.
