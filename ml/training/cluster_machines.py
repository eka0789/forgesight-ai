"""Machine behavior clustering experiments: KMeans (k selected by silhouette)
and DBSCAN (eps grid). Produces experiments.json consumed by the registry."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import joblib
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.common import AI4I_CSV, ARTIFACTS_DIR, report

FEATURES = [
    "air_temperature", "process_temperature", "rotational_speed",
    "torque", "tool_wear", "vibration",
    "temp_delta", "power_w", "wear_torque_product", "speed_torque_ratio",
]


def main() -> None:
    df = __import__("pandas").read_csv(AI4I_CSV)
    from app.services.pdm.features import add_engineered_features

    X = add_engineered_features(df)[FEATURES]
    X = X.sample(4000, random_state=42)
    print(f"clustering on {len(X)} rows, {len(FEATURES)} features")

    kmeans_results = {}
    best_k, best_score, best_pipe = None, -1.0, None
    for k in range(2, 7):
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=k, n_init=10, random_state=42)),
        ])
        labels = pipe.fit_predict(X)
        score = float(silhouette_score(X, labels))
        kmeans_results[f"k={k}"] = {"silhouette": round(score, 4), "sizes": np.bincount(labels).tolist()}
        if score > best_score:
            best_k, best_score, best_pipe = k, score, pipe
    print(f"[kmeans] best k={best_k} silhouette={best_score:.4f}")

    dbscan_results = {}
    for eps in (0.8, 1.0, 1.2, 1.5):
        pipe = Pipeline([("scaler", StandardScaler()), ("dbscan", DBSCAN(eps=eps, min_samples=10))])
        labels = pipe.fit_predict(X)
        n_clusters = len(set(labels) - {-1})
        noise = float((labels == -1).mean())
        dbscan_results[f"eps={eps}"] = {
            "n_clusters": n_clusters, "noise_ratio": round(noise, 4),
            "silhouette": round(float(silhouette_score(X, labels)) if n_clusters > 1 else 0.0, 4),
        }

    joblib.dump(best_pipe, ARTIFACTS_DIR / "clustering" / "kmeans.joblib")
    doc = {
        "version": "v1.0.0-" + datetime.now(UTC).strftime("%Y%m%d"),
        "kmeans": {"best_k": best_k, "best_silhouette": round(best_score, 4), "sweep": kmeans_results},
        "dbscan": {"sweep": dbscan_results},
        "metrics": {"silhouette": round(best_score, 4)},
        "params": {"features": FEATURES, "sample_rows": len(X)},
        "splits": {},
        "note": "Exploratory behavior segmentation — NOT used for production maintenance decisions.",
    }
    (ARTIFACTS_DIR / "clustering" / "experiments.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report("clustering experiments", doc)


if __name__ == "__main__":
    main()
