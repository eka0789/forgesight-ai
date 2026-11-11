"""Shared feature engineering for predictive-maintenance models.

IMPORTANT: this module is imported by BOTH the API (inference) and the
training scripts (ml/training) so that the pickled sklearn pipelines always
resolve a stable module path at load time. Changing feature definitions
requires retraining.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RAW_FEATURES = [
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear",
    "vibration",
]
ENGINEERED_FEATURES = [
    "temp_delta",
    "power_w",
    "wear_torque_product",
    "speed_torque_ratio",
]
ALL_FEATURES = RAW_FEATURES + ENGINEERED_FEATURES

DEFAULT_VIBRATION = 1.5


def payload_to_frame(payload: dict) -> pd.DataFrame:
    """Convert an API sensor payload into a one-row DataFrame with raw schema."""
    row = {
        "air_temperature": float(payload["air_temperature"]),
        "process_temperature": float(payload["process_temperature"]),
        "rotational_speed": float(payload["rotational_speed"]),
        "torque": float(payload["torque"]),
        "tool_wear": float(payload["tool_wear"]),
        "vibration": float(payload.get("vibration") if payload.get("vibration") is not None else DEFAULT_VIBRATION),
    }
    return pd.DataFrame([row])


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds physics-inspired features. Must stay in sync with training."""
    df = df.copy()
    df["temp_delta"] = df["process_temperature"] - df["air_temperature"]
    df["power_w"] = df["torque"] * df["rotational_speed"] * 2.0 * np.pi / 60.0
    df["wear_torque_product"] = df["tool_wear"] * df["torque"]
    df["speed_torque_ratio"] = df["rotational_speed"] / (df["torque"].clip(lower=0.1) + 1.0)
    return df


def make_features(payload: dict) -> pd.DataFrame:
    return add_engineered_features(payload_to_frame(payload))[ALL_FEATURES]
