"""Data-drift detection: PSI (Population Stability Index) per feature between
training reference stats and recent production readings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy.orm import Session

from app.models.machine import Machine, SensorReading
from app.services.pdm import inference as pdm


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index with quantile bins from the reference."""
    eps = 1e-6
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    e_hist = np.histogram(expected, bins=edges)[0] / max(1, len(expected))
    a_hist = np.histogram(actual, bins=edges)[0] / max(1, len(actual))
    e_hist = np.clip(e_hist, eps, None)
    a_hist = np.clip(a_hist, eps, None)
    return float(np.sum((a_hist - e_hist) * np.log(a_hist / e_hist)))


def drift_report(db: Session, org_id: int, days: int = 7) -> dict:
    pdm.artifacts.load()
    ref = (pdm.artifacts.failure_meta or {}).get("reference_stats")
    if not ref:
        return {"available": False,
                "note": "Reference statistics not found — retrain with ml/training/train_pdm_failure.py."}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(SensorReading)
        .join(Machine, Machine.id == SensorReading.machine_id)
        .filter(Machine.org_id == org_id, SensorReading.ts >= since)
        .all()
    )
    if len(rows) < 30:
        return {"available": False,
                "note": f"Only {len(rows)} readings in the last {days}d — at least 30 required."}

    features = {
        "air_temperature": [r.air_temperature for r in rows],
        "process_temperature": [r.process_temperature for r in rows],
        "rotational_speed": [r.rotational_speed for r in rows],
        "torque": [r.torque for r in rows],
        "tool_wear": [r.tool_wear for r in rows],
        "vibration": [r.vibration if r.vibration is not None else 1.5 for r in rows],
    }
    per_feature = {}
    max_psi = 0.0
    for name, values in features.items():
        if name not in ref:
            continue
        p = psi(np.asarray(ref[name], dtype=float), np.asarray(values, dtype=float))
        per_feature[name] = round(p, 4)
        max_psi = max(max_psi, p)

    verdict = "stable" if max_psi < 0.1 else ("moderate drift" if max_psi < 0.25 else "significant drift")
    return {
        "available": True,
        "window_days": days,
        "n_readings": len(rows),
        "psi_per_feature": per_feature,
        "max_psi": round(max_psi, 4),
        "verdict": verdict,
        "note": "PSI < 0.1 stable; 0.1–0.25 moderate; > 0.25 significant (industry rule of thumb).",
    }
