"""Procedurally generated synthetic industrial surface images.

Clearly labeled SYNTHETIC: used for demo data and the trainable CNN dataset
(clean / scratch / stain / dent). Not a substitute for real production imagery.
"""
from __future__ import annotations

import cv2
import numpy as np

CLASSES = ["clean", "scratch", "stain", "dent"]
SIZE = 224


def _metal_base(rng: np.random.Generator, size: int = SIZE) -> np.ndarray:
    base = np.full((size, size), 138, dtype=np.float32)
    base += rng.normal(0, 8, (size, size))
    yy, xx = np.mgrid[0:size, 0:size]
    base += 6 * np.sin(xx / 9.0) + 4 * np.sin(yy / 13.0)
    img = np.clip(base, 0, 255).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def generate_defect_image(kind: str, seed: int = 0, size: int = SIZE) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = _metal_base(rng, size)
    if kind == "scratch":
        for _ in range(rng.integers(2, 5)):
            x0, y0 = rng.integers(0, size, 2)
            length = rng.integers(size // 5, size // 2)
            angle = rng.uniform(0, np.pi)
            x1 = int(x0 + length * np.cos(angle))
            y1 = int(y0 + length * np.sin(angle))
            cv2.line(img, (int(x0), int(y0)), (x1, y1), (225, 225, 230), rng.integers(1, 3))
    elif kind == "stain":
        cx, cy = rng.integers(size // 4, 3 * size // 4, 2)
        r = int(rng.integers(size // 6, size // 4))
        color = int(rng.integers(60, 95))
        cv2.circle(img, (int(cx), int(cy)), r, (color, color - 10, color - 20), -1)
        img = cv2.GaussianBlur(img, (0, 0), 2.5)
        # re-add fine noise so blur does not erase texture everywhere
        noise = rng.normal(0, 4, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    elif kind == "dent":
        cx, cy = rng.integers(size // 4, 3 * size // 4, 2)
        r = int(rng.integers(size // 8, size // 5))
        cv2.circle(img, (int(cx), int(cy)), r, (90, 85, 80), -1)
        img = cv2.GaussianBlur(img, (0, 0), 3.0)
        cv2.circle(img, (int(cx), int(cy)), max(2, r // 3), (60, 55, 50), -1)
    return img
