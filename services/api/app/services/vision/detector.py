"""Defect detection layer.

Priority order (honest method labeling on every response):
1. YOLO (ultralytics) when installed AND a local weights file is provided.
2. Classical unsupervised surface-anomaly grid (OpenCV) — always available:
   robust per-tile statistics against the image's own baseline; real CV method,
   not a mock.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.vision.preprocessing import enhance, resize_max

TILE = 64
SEVERITY_THRESHOLDS = [(2.8, "low"), (3.4, "medium"), (4.2, "high")]


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple[int, int, int, int] | None
    severity: str


def severity_for(z: float) -> str:
    for limit, sev in SEVERITY_THRESHOLDS:
        if z < limit:
            return sev
    return "critical"


class ClassicalAnomalyDetector:
    """Unsupervised tile-level anomaly localization (median/MAD z-score)."""

    method = "classical_anomaly_grid"

    def detect(self, gray: np.ndarray, z_threshold: float = 2.8) -> list[Detection]:
        h, w = gray.shape[:2]
        tiles: list[tuple[int, int, np.ndarray]] = []
        for y in range(0, h - TILE + 1, TILE):
            for x in range(0, w - TILE + 1, TILE):
                tiles.append((x, y, gray[y : y + TILE, x : x + TILE]))

        if len(tiles) < 4:
            return []
        means = np.array([t.mean() for _, _, t in tiles])
        stds = np.array([t.std() for _, _, t in tiles])
        med_mean, mad_mean = np.median(means), 1.4826 * np.median(np.abs(means - np.median(means))) + 1e-6
        med_std, mad_std = np.median(stds), 1.4826 * np.median(np.abs(stds - np.median(stds))) + 1e-6

        detections: list[Detection] = []
        for (x, y, tile), m, s in zip(tiles, means, stds):
            z_m = abs(m - med_mean) / mad_mean
            z_s = abs(s - med_std) / mad_std
            z = max(z_m, z_s)
            if z >= z_threshold:
                detections.append(
                    Detection(
                        label="surface_anomaly",
                        confidence=round(min(0.99, 0.5 + 0.12 * (z - z_threshold)), 3),
                        bbox=(x, y, x + TILE, y + TILE),
                        severity=severity_for(z),
                    )
                )
        return detections


class YoloDetector:
    """YOLO path — only active when ultralytics + weights are available."""

    def __init__(self, weights_path: str):
        from ultralytics import YOLO  # guarded import

        self.model = YOLO(weights_path)
        self.method = "yolo"

    def detect(self, img_bgr: np.ndarray, confidence: float = 0.4) -> list[Detection]:
        results = self.model.predict(img_bgr, conf=confidence, verbose=False)
        out: list[Detection] = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                out.append(
                    Detection(
                        label=r.names.get(int(box.cls[0]), "object"),
                        confidence=round(float(box.conf[0]), 3),
                        bbox=(x1, y1, x2, y2),
                        severity="medium",
                    )
                )
        return out


class DetectionRouter:
    """Chooses the best available detector for this deployment."""

    def __init__(self, weights_path: str | None = None):
        self._yolo: YoloDetector | None = None
        if weights_path:
            try:
                self._yolo = YoloDetector(weights_path)
            except Exception:
                self._yolo = None
        self.classical = ClassicalAnomalyDetector()

    @property
    def method_name(self) -> str:
        return self._yolo.method if self._yolo else self.classical.method

    def detect(self, img_bgr: np.ndarray, z_threshold: float = 2.8, confidence: float = 0.4) -> list[Detection]:
        resized = resize_max(img_bgr)
        if self._yolo is not None:
            return self._yolo.detect(resized, confidence=confidence)
        return self.classical.detect(enhance(resized), z_threshold=z_threshold)
