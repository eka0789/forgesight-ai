"""Machine failure classification — real training, honest metrics.

Models: LogisticRegression (baseline), RandomForest, HistGradientBoosting,
XGBoost (optional). Selection on validation F1 (imbalanced target), final
evaluation on a held-out test split. Artifacts saved for API inference.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.common import (
    AI4I_CSV,
    ARTIFACTS_DIR,
    mlflow_finish,
    mlflow_setup,
    report,
    sha256_file,
)

SEED = 42
ALIAS = {
    "Air temperature [K]": "air_temperature",
    "Process temperature [K]": "process_temperature",
    "Rotational speed [rpm]": "rotational_speed",
    "Torque [Nm]": "torque",
    "Tool wear [min]": "tool_wear",
    "Machine failure": "machine_failure",
}
FEATURES = [
    "air_temperature", "process_temperature", "rotational_speed",
    "torque", "tool_wear", "vibration",
    "temp_delta", "power_w", "wear_torque_product", "speed_torque_ratio",
]


def load_dataset() -> pd.DataFrame:
    df = pd.read_csv(AI4I_CSV)
    df = df.rename(columns=ALIAS)
    return df


def metrics_of(y_true, y_score, y_pred, elapsed_per_k: float) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_score)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_score)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "latency_ms_per_1k": round(elapsed_per_k, 2),
    }


def evaluate(name: str, model, X, y, train_ref: np.ndarray) -> dict:
    t0 = time.perf_counter()
    y_score = model.predict_proba(X)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)
    per_k = (time.perf_counter() - t0) / len(X) * 1000 * 1000
    return metrics_of(y, y_score, y_pred, per_k)


def build_candidates(n_pos: int, n_neg: int) -> dict:
    candidates: dict = {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=SEED)),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
            n_jobs=-1, random_state=SEED,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, random_state=SEED,
        ),
    }
    try:
        from xgboost import XGBClassifier

        candidates["xgboost"] = XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.08,
            scale_pos_weight=n_neg / max(1, n_pos), tree_method="hist",
            eval_metric="logloss", random_state=SEED, n_jobs=-1, verbosity=0,
        )
    except ImportError:
        print("[info] xgboost not installed — skipping (HistGB covers boosted trees)")
    return candidates


def main() -> None:
    df = load_dataset()
    y = df["machine_failure"].values

    from app.services.pdm.features import add_engineered_features  # shared with API

    feats = add_engineered_features(df)[FEATURES]
    print(f"dataset: {len(df)} rows, failure rate {y.mean():.3%}, features={len(FEATURES)}")

    # stratified 60/20/20, no leakage: split BEFORE any scaling (LR scaler is inside pipeline)
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(df))
    n = len(df)
    i_train, i_val, i_test = idx[: int(0.6 * n)], idx[int(0.6 * n): int(0.8 * n)], idx[int(0.8 * n):]
    X_train, y_train = feats.iloc[i_train], y[i_train]
    X_val, y_val = feats.iloc[i_val], y[i_val]
    X_test, y_test = feats.iloc[i_test], y[i_test]

    candidates = build_candidates(int(y_train.sum()), int((1 - y_train).sum()))
    results: dict[str, dict] = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        results[name] = evaluate(name, model, X_val, y_val, X_train.values)
        print(f"[val] {name}: f1={results[name]['f1']} recall={results[name]['recall']} roc_auc={results[name]['roc_auc']}")

    best_name = max(results, key=lambda k: results[k]["f1"])
    print(f"[select] best by validation F1: {best_name}")

    # refit best on train+val, evaluate on untouched test
    best = candidates[best_name]
    best.fit(pd.concat([X_train, X_val]), np.concatenate([y_train, y_val]))
    test_metrics = evaluate(best_name, best, X_test, y_test, X_train.values)
    print(f"[test] {best_name}: {json.dumps({k: v for k, v in test_metrics.items() if k != 'confusion_matrix'})}")

    version = "v1.0.0-" + datetime.now(UTC).strftime("%Y%m%d")
    ref_stats = {f: np.asarray(feats[f].sample(1000, random_state=SEED)).tolist() for f in FEATURES}

    bundle = {
        "pipeline": best,
        "meta": {
            "version": version,
            "model_type": best_name,
            "feature_names": FEATURES,
            "metrics": {"test": {k: v for k, v in test_metrics.items() if k != "confusion_matrix"},
                        "val": {k: v for k, v in results[best_name].items() if k != "confusion_matrix"}},
            "reference_stats": ref_stats,
            "trained_at": datetime.now(UTC).isoformat(),
            "dataset": {"name": AI4I_CSV.name, "sha256": sha256_file(AI4I_CSV), "rows": len(df),
                        "is_synthetic": not (AI4I_CSV.parent / "ai4i_real.csv").exists()},
        },
    }
    out = ARTIFACTS_DIR / "pdm"
    joblib.dump(bundle, out / "failure_model.joblib")
    metrics_doc = {
        "failure": {
            "version": version,
            "model_type": best_name,
            "metrics": {"test": test_metrics},
            "params": {"models_compared": list(results.keys()), "selection_metric": "val_f1",
                       "imbalance_strategy": "class_weight/balanced or scale_pos_weight"},
            "splits": {"val": results[best_name], "test": test_metrics},
            "dataset": bundle["meta"]["dataset"],
        }
    }
    (out / "metrics.json").write_text(json.dumps(metrics_doc, indent=2, default=str), encoding="utf-8")

    mlflow, run = mlflow_setup("pdm-failure")
    if mlflow:
        mlflow.log_params({"model": best_name, "dataset": "ai4i_synthetic", "features": len(FEATURES)})
        for k, v in test_metrics.items():
            if isinstance(v, (int, float)):
                mlflow.log_metric(f"test_{k}", v)
        mlflow.log_artifact(str(out / "failure_model.joblib"))
        mlflow_finish(mlflow, run)

    report("failure classifier", metrics_doc["failure"])


if __name__ == "__main__":
    main()
