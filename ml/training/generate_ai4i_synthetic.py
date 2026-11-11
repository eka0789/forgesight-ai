"""SYNTHETIC AI4I-style dataset generator (deterministic, documented).

Schema mirrors the public *AI4I 2020 Predictive Maintenance Dataset* (UCI):
5 sensor channels + machine_failure + failure modes (TWF/HDF/PWF/OSF/RNF)
with the generator's documented physical thresholds:
  TWF: tool wear in [200, 240] min
  HDF: (process - air temp) < 8.6K AND rotational speed < 1380 rpm
  PWF: power (torque * speed) outside [3500, 9000] W
  OSF: tool_wear * torque > 11,000–13,000 minNm

This is NOT the original dataset: if you drop the real CSV at
ml/datasets/ai4i_real.csv, training scripts load it automatically (column
aliases handled). Synthetic data is clearly labeled everywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.training.common import AI4I_CSV, report


def generate(n: int = 10_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    air = rng.normal(300.0, 2.0, n)
    # temperature delta concentrated around 10K with a cooler tail (HDF zone)
    delta = np.where(rng.random(n) < 0.12, rng.normal(8.0, 0.6, n), rng.normal(10.2, 1.1, n))
    process = air + delta

    torque = rng.normal(40.0, 10.0, n).clip(2.0)
    speed = (1500.0 - 5.0 * (torque - 40.0) + rng.normal(0.0, 120.0, n)).clip(1100.0, 2400.0)

    # bimodal tool wear: mostly fresh tools + a worn cohort (drives TWF/OSF)
    wear = np.where(
        rng.random(n) < 0.85, rng.normal(100.0, 40.0, n), rng.normal(215.0, 12.0, n)
    ).clip(0.0, 265.0)

    vibration = (rng.normal(1.5, 0.5, n) + np.where(torque > 60.0, 0.6, 0.0)).clip(0.1, 8.0)

    power = torque * speed * 2.0 * np.pi / 60.0
    twf = (wear > 200.0) & (wear < 240.0) & (rng.random(n) < 0.8)
    hdf = (delta < 8.6) & (speed < 1380.0) & (rng.random(n) < 0.85)
    pwf = ((power < 3500.0) | (power > 9000.0)) & (rng.random(n) < 0.85)
    osf = (wear * torque > 11_000.0) & (rng.random(n) < 0.85)
    rnf = rng.random(n) < 0.001
    machine_failure = twf | hdf | pwf | osf | rnf

    return pd.DataFrame({
        "air_temperature": air.round(2),
        "process_temperature": process.round(2),
        "rotational_speed": speed.round(1),
        "torque": torque.round(2),
        "tool_wear": wear.round(1),
        "vibration": vibration.round(3),
        "TWF": twf.astype(int),
        "HDF": hdf.astype(int),
        "PWF": pwf.astype(int),
        "OSF": osf.astype(int),
        "RNF": rnf.astype(int),
        "machine_failure": machine_failure.astype(int),
    })


def main() -> None:
    real = AI4I_CSV.parent / "ai4i_real.csv"
    if real.exists():
        df = pd.read_csv(real)
        df.to_csv(AI4I_CSV, index=False)
        report("AI4I (REAL dataset detected — copied)", {"rows": len(df)})
        return
    df = generate()
    df.to_csv(AI4I_CSV, index=False)
    report("AI4I-style SYNTHETIC dataset", {
        "path": str(AI4I_CSV),
        "rows": len(df),
        "failure_rate": round(float(df["machine_failure"].mean()), 4),
        "mode_counts": {m: int(df[m].sum()) for m in ["TWF", "HDF", "PWF", "OSF", "RNF"]},
        "note": "Synthetic mirror of AI4I 2020 schema with documented thresholds.",
    })


if __name__ == "__main__":
    main()
