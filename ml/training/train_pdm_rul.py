"""RUL (Remaining Useful Life) regression — synthetic C-MAPSS-style degradation.

Generates unit-level degradation trajectories (deterministic seed), trains
RandomForest vs HistGradientBoosting, evaluates MAE/RMSE/R², saves the best
pipeline for API inference. Clearly labeled SYNTHETIC; drop the real C-MAPSS
files into ml/datasets/ and adapt `load_or_generate` for the real set.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.training.common import ARTIFACTS_DIR, RUL_CSV, report, sha256_file

SEED = 42
FEATURES = [
    "air_temperature", "process_temperature", "rotational_speed",
    "torque", "tool_wear", "vibration",
    "temp_delta", "power_w", "wear_torque_product", "speed_torque_ratio",
]


def generate(n_units: int = 260, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for unit in range(n_units):
        life = rng.integers(140, 320)
        load = rng.uniform(0.75, 1.35)
        for t in range(life):
            frac = t / life
            air = rng.normal(300, 2)
            process = air + rng.normal(10 + 2.5 * frac * load, 1.0)
            speed = float(np.clip(rng.normal(1500 / load, 110), 1000.0, 2400.0))
            torque = rng.normal(40 * load, 9)
            wear = min(265.0, 250 * frac + rng.normal(0, 6))
            vibration = float(np.clip(1.0 + 2.4 * frac**2 * load + rng.normal(0, 0.15), 0.1, None))
            rows.append({
                "unit": unit, "cycle": t,
                "air_temperature": round(air, 2), "process_temperature": round(process, 2),
                "rotational_speed": round(float(speed), 1), "torque": round(torque, 2),
                "tool_wear": round(wear, 1), "vibration": round(vibration, 3),
                "rul": life - t,
            })
    return pd.DataFrame(rows)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    from app.services.pdm.features import add_engineered_features

    return add_engineered_features(df)


def main() -> None:
    real = RUL_CSV.parent / "cmapps_real.csv"
    if real.exists():
        df = pd.read_csv(real)
        source = "cmapps_real"
    else:
        df = generate()
        df.to_csv(RUL_CSV, index=False)
        source = "cmapps_synthetic"

    df = add_features(df)
    y = df["rul"].values

    rng = np.random.default_rng(SEED)
    units = df["unit"].unique()
    rng.shuffle(units)
    n = len(units)
    u_train, u_test = units[: int(0.8 * n)], units[int(0.8 * n):]
    m_train, m_test = df["unit"].isin(u_train), df["unit"].isin(u_test)
    X_train, y_train = df[m_train][FEATURES], y[m_train]
    X_test, y_test = df[m_test][FEATURES], y[m_test]
    print(f"rows={len(df)} train_units={len(u_train)} test_units={len(u_test)}")

    candidates = {
        "random_forest": RandomForestRegressor(n_estimators=250, min_samples_leaf=3, n_jobs=-1, random_state=SEED),
        "hist_gradient_boosting": HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08, random_state=SEED),
    }
    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        results[name] = {
            "mae": round(float(mean_absolute_error(y_test, pred)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, pred))), 3),
            "r2": round(float(r2_score(y_test, pred)), 4),
        }
        print(f"[test] {name}: {results[name]}")

    best_name = min(results, key=lambda k: results[k]["mae"])
    best = candidates[best_name]
    version = "v1.0.0-" + datetime.now(UTC).strftime("%Y%m%d")

    bundle = {
        "pipeline": best,
        "meta": {
            "version": version, "model_type": best_name, "feature_names": FEATURES,
            "metrics": {"test": results[best_name]},
            "trained_at": datetime.now(UTC).isoformat(),
            "dataset": {"name": RUL_CSV.name, "sha256": sha256_file(RUL_CSV),
                        "rows": len(df), "is_synthetic": source == "cmapps_synthetic"},
        },
    }
    out = ARTIFACTS_DIR / "pdm"
    joblib.dump(bundle, out / "rul_model.joblib")
    doc = {"rul": {"version": version, "model_type": best_name,
                   "metrics": {"test": results[best_name]},
                   "params": {"models_compared": list(results.keys())},
                   "splits": {"test": results[best_name]},
                   "dataset": bundle["meta"]["dataset"]}}
    (out / "metrics.json").write_text(
        json.dumps({**(json.loads((out / 'metrics.json').read_text()) if (out / 'metrics.json').exists() else {}), **doc},
                   indent=2, default=str),
        encoding="utf-8",
    )
    report("RUL regressor", doc["rul"])


if __name__ == "__main__":
    main()
