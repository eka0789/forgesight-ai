#!/usr/bin/env bash
# ForgeSight AI — full training pipeline (CPU-friendly).
# Usage: bash scripts/train_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python}
if [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"; fi
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

echo "==> Generating datasets"
"$PY" -m ml.training.generate_ai4i_synthetic
echo "==> Failure classification"
"$PY" -m ml.training.train_pdm_failure
echo "==> RUL regression"
"$PY" -m ml.training.train_pdm_rul
echo "==> Clustering experiments"
"$PY" -m ml.training.cluster_machines
echo "==> Vision CNN (torch optional)"
"$PY" -m ml.training.train_vision_classifier || true
echo "==> Anomaly autoencoder (torch optional)"
"$PY" -m ml.training.train_anomaly_ae || true

echo "==> Registering models into API registry"
"$PY" -c "import sys; sys.path.insert(0, 'services/api'); \
from app.db.session import SessionLocal; from app.services.mlops.registry import register_all; \
print(register_all(SessionLocal()))"

echo "All training complete. Artifacts in ml/artifacts."
