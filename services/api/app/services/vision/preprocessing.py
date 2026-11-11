"""OpenCV preprocessing primitives used by every inspection path."""
from __future__ import annotations

import base64

import cv2
import numpy as np

MAX_SIDE = 1024


def decode_image(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def to_data_url(img: np.ndarray) -> str:
    return "data:image/png;base64," + base64.b64encode(encode_png(img)).decode("ascii")


def resize_max(img: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1.0:
        return img
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def enhance(img: np.ndarray) -> np.ndarray:
    """Grayscale CLAHE + mild denoise — standard industrial prep."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.fastNlMeansDenoising(enhanced, None, h=7, templateWindowSize=7, searchWindowSize=15)


def annotated_overlay(original: np.ndarray, boxes: list[dict]) -> np.ndarray:
    out = original.copy()
    for b in boxes:
        x1, y1, x2, y2 = b.get("bbox_x1"), b.get("bbox_y1"), b.get("bbox_x2"), b.get("bbox_y2")
        if None in (x1, y1, x2, y2):
            continue
        color = (0, 90, 255) if (b.get("severity") or "medium") in ("high", "critical") else (60, 160, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(out, f"{b.get('label','defect')} {b.get('confidence', 0):.2f}", (x1, max(12, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return out
