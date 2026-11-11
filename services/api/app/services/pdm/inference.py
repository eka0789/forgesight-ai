"""Predictive-maintenance inference: loads real trained artifacts (joblib) and
serves failure probability, per-mode risk estimates, RUL, health score and
recommendations. When artifacts are missing the service reports clearly that
prediction is unavailable (never fabricates model output)."""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import joblib

from app.core.config import settings
from app.services.pdm.features import make_features


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class PDMArtifacts:
    def __init__(self) -> None:
        self.failure_model: Any | None = None
        self.failure_meta: dict | None = None
        self.rul_model: Any | None = None
        self.rul_meta: dict | None = None
        self.kmeans: Any | None = None
        self.loaded = False
        self.error: str | None = None

    def load(self) -> None:
        if self.loaded:
            return
        base = Path(settings.resolved_artifacts_dir)
        try:
            fpath = base / "pdm" / "failure_model.joblib"
            if fpath.exists():
                bundle = joblib.load(fpath)
                self.failure_model = bundle["pipeline"]
                self.failure_meta = bundle.get("meta", {})
            rpath = base / "pdm" / "rul_model.joblib"
            if rpath.exists():
                bundle = joblib.load(rpath)
                self.rul_model = bundle["pipeline"]
                self.rul_meta = bundle.get("meta", {})
            kpath = base / "clustering" / "kmeans.joblib"
            if kpath.exists():
                self.kmeans = joblib.load(kpath)
            self.loaded = True
        except Exception as exc:  # keep API alive, report honestly
            self.error = f"Artifact load failed: {exc}"

    @property
    def failure_version(self) -> str | None:
        return (self.failure_meta or {}).get("version")

    @property
    def rul_version(self) -> str | None:
        return (self.rul_meta or {}).get("version")


artifacts = PDMArtifacts()


def mode_probabilities(feat: dict) -> dict[str, float]:
    """Rule-based per-failure-mode estimates (AI4I 2020 failure-mode thresholds).

    These are *documented heuristics* blended with the trained model's overall
    probability — the API labels them as such. From the AI4I dataset generator:
      TWF: tool wear in [200, 240] min
      HDF: temp delta < 8.6 K AND rotational speed < 1380 rpm
      PWF: power < 3500 W or > 9000 W
      OSF: tool_wear * torque > 11,000–13,000 minNm (tool class dependent)
    """
    tw = feat["tool_wear"]
    delta = feat["process_temperature"] - feat["air_temperature"]
    speed = feat["rotational_speed"]
    torque = feat["torque"]
    power = torque * speed * 2.0 * math.pi / 60.0
    wear_torque = tw * torque

    twf = _sigmoid(-((tw - 220.0) ** 2) / 200.0) * (0.6 if 200 <= tw <= 240 else 0.0)
    hdf = _sigmoid((8.6 - delta) / 0.8) * _sigmoid((1380.0 - speed) / 60.0)
    if 3500.0 <= power <= 9000.0:
        pwf = 0.02
    elif power < 3500.0:
        pwf = _sigmoid((3500.0 - power) / 300.0)
    else:
        pwf = _sigmoid((power - 9000.0) / 600.0)
    osf = _sigmoid((wear_torque - 12000.0) / 800.0)
    rnf = 0.001

    return {k: round(float(v), 4) for k, v in {
        "TWF": max(twf, 0.0), "HDF": max(hdf, 0.0),
        "PWF": max(pwf, 0.0), "OSF": max(osf, 0.0), "RNF": rnf,
    }.items()}


def risk_level(p: float) -> str:
    if p < 0.2:
        return "low"
    if p < 0.5:
        return "medium"
    if p < 0.8:
        return "high"
    return "critical"


RECOMMENDATIONS: dict[str, str] = {
    "TWF": "Tool wear is approaching end-of-life: schedule tool replacement within the next shift.",
    "HDF": "Heat dissipation degraded: inspect the cooling system and verify ambient temperature control.",
    "PWF": "Spindle power draw outside nominal band: verify motor drive and mechanical load.",
    "OSF": "Overstrain risk (wear x torque product high): reduce cutting load or inspect tool condition.",
    "RNF": "Process-random failure signal: review quality of upstream material and recent process changes.",
}


def predict_failure(payload: dict) -> dict:
    t0 = time.perf_counter()
    artifacts.load()
    modes = mode_probabilities(payload)
    df = make_features(payload)

    if artifacts.failure_model is None:
        # Honest degradation: rule-based estimate only, clearly labeled.
        p_rule = min(1.0, sum(modes.values()) * 0.5)
        return {
            "failure_probability": round(p_rule, 4),
            "risk_level": risk_level(p_rule),
            "predicted_modes": modes,
            "top_factors": [],
            "model_version": "rules-only-fallback",
            "model_metrics": None,
            "recommendations": [
                RECOMMENDATIONS[max(modes, key=modes.get)],
                "NOTE: trained model artifact not found — rule-based estimate only. Run ml/training/train_pdm_failure.py.",
            ],
            "inference_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    prob = float(artifacts.failure_model.predict_proba(df)[0][1])
    # Blend overall model probability with mode heuristics (30% weight).
    p_final = 0.7 * prob + 0.3 * min(1.0, sum(modes.values()) * 0.5)

    top_factors: list[dict] = []
    try:
        names = artifacts.failure_meta.get("feature_names", [])
        importances = getattr(artifacts.failure_model[-1], "feature_importances_", None)
        if importances is None and hasattr(artifacts.failure_model[-1], "coef_"):
            importances = abs(artifacts.failure_model[-1].coef_[0])
        if importances is not None and names:
            pairs = sorted(zip(names, [float(i) for i in importances]), key=lambda x: -x[1])
            top_factors = [{"feature": n, "importance": round(v, 4)} for n, v in pairs[:5]]
    except Exception:
        pass

    return {
        "failure_probability": round(p_final, 4),
        "risk_level": risk_level(p_final),
        "predicted_modes": modes,
        "top_factors": top_factors,
        "model_version": artifacts.failure_version,
        "model_metrics": (artifacts.failure_meta or {}).get("metrics"),
        "recommendations": [RECOMMENDATIONS[m] for m, v in sorted(modes.items(), key=lambda x: -x[1]) if v >= 0.3]
        or ["Machine parameters are within nominal bands; continue standard monitoring."],
        "inference_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


def predict_rul(payload: dict, cycles_elapsed: float | None = None) -> dict:
    t0 = time.perf_counter()
    artifacts.load()
    df = make_features(payload)
    if artifacts.rul_model is None:
        raise RuntimeError("RUL model artifact not found — run ml/training/train_pdm_rul.py")
    rul_cycles = float(artifacts.rul_model.predict(df)[0])
    rul_hours = max(0.0, rul_cycles)
    if cycles_elapsed is not None:
        rul_hours = max(0.0, min(rul_hours, 10_000.0 - float(cycles_elapsed)))
    return {
        "rul_hours": round(rul_hours, 1),
        "model_version": artifacts.rul_version,
        "model_metrics": (artifacts.rul_meta or {}).get("metrics"),
        "inference_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


def health_score(failure_result: dict, rul_hours: float | None) -> float:
    """Documented composite: 70% (1 - failure prob) + 30% RUL headroom (720h ref)."""
    p = float(failure_result["failure_probability"])
    if rul_hours is None:
        return round(100.0 * (1.0 - p) ** 0.9, 1)
    rul_factor = min(max(rul_hours, 0.0), 720.0) / 720.0
    return round(100.0 * (0.7 * (1.0 - p) + 0.3 * rul_factor), 1)


def behavior_segment(payload: dict) -> str | None:
    artifacts.load()
    if artifacts.kmeans is None:
        return None
    df = make_features(payload)
    try:
        return f"segment_{int(artifacts.kmeans.predict(df)[0])}"
    except Exception:
        return None
