"""Model registry bootstrap — reads trained-artifact metric reports produced by
ml/training scripts and registers them as MLModel/MLModelVersion rows (idempotent).

Artifact directory convention:
  ml/artifacts/pdm/metrics.json            -> failure_classifier + rul_regressor
  ml/artifacts/clustering/experiments.json -> machine_behavior
  ml/artifacts/vision/cnn_metrics.json     -> defect_cnn
  ml/artifacts/vision/ae_metrics.json      -> anomaly_ae
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.mlops import MLModel, MLModelVersion, ModelMetric

REGISTRY_MAP: list[dict] = [
    {"name": "failure_classifier", "task": "tabular_classification", "framework": "sklearn",
     "desc": "Machine failure classification (AI4I-style engineered features).",
     "metrics_path": ("pdm", "metrics.json"), "key": "failure"},
    {"name": "rul_regressor", "task": "rul_regression", "framework": "sklearn",
     "desc": "Remaining Useful Life regression from sensor features.",
     "metrics_path": ("pdm", "metrics.json"), "key": "rul"},
    {"name": "machine_behavior", "task": "clustering", "framework": "sklearn",
     "desc": "KMeans/DBSCAN machine behavior segmentation experiments.",
     "metrics_path": ("clustering", "experiments.json"), "key": None},
    {"name": "defect_cnn", "task": "image_classification", "framework": "pytorch",
     "desc": "Synthetic surface-defect CNN (clean/scratch/stain/dent).",
     "metrics_path": ("vision", "cnn_metrics.json"), "key": None},
    {"name": "anomaly_ae", "task": "anomaly_detection", "framework": "pytorch",
     "desc": "Autoencoder anomaly scoring on surface images.",
     "metrics_path": ("vision", "ae_metrics.json"), "key": None},
]

DEFAULT_STATUS = {
    "failure_classifier": "production",
    "rul_regressor": "production",
    "machine_behavior": "staging",
    "defect_cnn": "staging",
    "anomaly_ae": "staging",
}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def register_all(db: Session, *, created_by: str = "system") -> dict:
    base = Path(settings.resolved_artifacts_dir)
    registered: list[str] = []

    for spec in REGISTRY_MAP:
        subdir, filename = spec["metrics_path"]
        doc = _read_json(base / subdir / filename)
        if not doc:
            continue

        if spec["key"]:
            doc = doc.get(spec["key"], doc)

        model = db.query(MLModel).filter(MLModel.name == spec["name"]).first()
        if model is None:
            model = MLModel(name=spec["name"], task=spec["task"], description=spec["desc"])
            db.add(model)
            db.flush()

        version_label = doc.get("version", "v1")
        exists = (
            db.query(MLModelVersion)
            .filter(MLModelVersion.model_id == model.id, MLModelVersion.version == version_label)
            .first()
        )
        if exists:
            continue

        version = MLModelVersion(
            model_id=model.id,
            version=version_label,
            artifact_path=str(base / subdir),
            framework=spec["framework"],
            status=DEFAULT_STATUS.get(spec["name"], "registered"),
            metrics=doc.get("metrics"),
            params=doc.get("params"),
            created_by=created_by,
        )
        db.add(version)
        db.flush()
        for split, metrics in (doc.get("splits") or {}).items():
            if isinstance(metrics, dict):
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        db.add(ModelMetric(
                            model_version_id=version.id, split=split,
                            name=metric_name, value=float(value),
                        ))
        registered.append(f"{spec['name']}:{version_label}")

    db.commit()
    return {"registered": registered}
