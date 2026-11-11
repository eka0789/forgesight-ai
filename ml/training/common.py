"""Shared helpers for training scripts: paths, dataset loading, MLflow wiring."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

ML_DIR = REPO_ROOT / "ml"
DATASETS_DIR = ML_DIR / "datasets"
ARTIFACTS_DIR = ML_DIR / "artifacts"

for d in (DATASETS_DIR, ARTIFACTS_DIR / "pdm", ARTIFACTS_DIR / "clustering", ARTIFACTS_DIR / "vision"):
    d.mkdir(parents=True, exist_ok=True)

AI4I_CSV = DATASETS_DIR / "ai4i_synthetic.csv"
RUL_CSV = DATASETS_DIR / "cmapps_synthetic_rul.csv"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def mlflow_setup(experiment: str):
    """Returns (mlflow module, run function) or (None, None) when unavailable."""
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        return None, None
    try:
        import mlflow

        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        return mlflow, mlflow.start_run()
    except Exception as exc:  # noqa: BLE001 — mlflow optional; any failure disables tracking
        print(f"[mlflow] unavailable ({exc}) — continuing without experiment tracking")
        return None, None


def mlflow_finish(mlflow, run) -> None:
    if mlflow and run:
        mlflow.end_run()


def report(title: str, payload: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str))
