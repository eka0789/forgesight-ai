"""Inspection pipeline orchestrator.

Every response item is labeled with the concrete method that produced it
(yolo / classical_anomaly_grid / cnn / autoencoder / tesseract / ...) so the
platform never overstates its capability.
"""
from __future__ import annotations

import os
import time

import cv2
import numpy as np

from app.services.vision.anomaly import ae_anomaly, classical_score
from app.services.vision.classifier import classifier
from app.services.vision.detector import DetectionRouter
from app.services.vision.ocr import ocr_text
from app.services.vision.preprocessing import annotated_overlay, decode_image, resize_max

VIDEO_MAX_FRAMES = 30

_detector: DetectionRouter | None = None


def _get_detector() -> DetectionRouter:
    """Lazy singleton — with YOLO weights configured this avoids reloading the
    model on every request."""
    global _detector
    if _detector is None:
        weights = os.environ.get("VISION_YOLO_WEIGHTS")
        _detector = DetectionRouter(weights_path=weights or None)
    return _detector


def inspect_image(img_bgr: np.ndarray, *, do_ocr: bool = False) -> dict:
    t0 = time.perf_counter()
    detector = _get_detector()

    detections = detector.detect(img_bgr)
    det_dicts = [
        {
            "label": d.label,
            "confidence": d.confidence,
            "bbox_x1": d.bbox[0] if d.bbox else None,
            "bbox_y1": d.bbox[1] if d.bbox else None,
            "bbox_x2": d.bbox[2] if d.bbox else None,
            "bbox_y2": d.bbox[3] if d.bbox else None,
            "severity": d.severity,
            "method": detector.method_name,
        }
        for d in detections
    ]

    classification = classifier.predict(resize_max(img_bgr))
    anomaly = ae_anomaly.score(resize_max(img_bgr)) or classical_score(resize_max(img_bgr))
    ocr = ocr_text(img_bgr) if do_ocr else None

    processing_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "method_used": detector.method_name,
        "detections": det_dicts,
        "classification": classification,
        "anomaly": anomaly,
        "ocr": ocr,
        "processing_ms": processing_ms,
        "model_version": (classification or {}).get("version") or "classical-cv-1.0",
    }


def inspect_image_bytes(data: bytes, *, do_ocr: bool = False) -> dict:
    img = decode_image(data)
    if img is None:
        raise ValueError("Unsupported or corrupted image data")
    return inspect_image(img, do_ocr=do_ocr)


def inspect_video_bytes(data: bytes, filename: str) -> dict:
    """Samples up to VIDEO_MAX_FRAMES evenly-spaced frames and aggregates the
    per-frame pipeline. Synchronous CPU processing — kicked off as a background
    task by the API layer."""
    t0 = time.perf_counter()
    import tempfile
    from pathlib import Path

    suffix = Path(filename).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    cap = None
    try:
        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise ValueError("Unsupported or corrupted video data")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            raise ValueError("Video has no readable frames")
        n = min(VIDEO_MAX_FRAMES, max(1, total))
        step = max(1, total // n)
        frames_processed = 0
        all_detections: list[dict] = []
        defect_frames = 0
        anomaly_scores: list[float] = []
        for idx in range(0, total, step):
            if frames_processed >= n:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            res = inspect_image(frame)
            frames_processed += 1
            if res["detections"]:
                defect_frames += 1
            for d in res["detections"]:
                d["frame_index"] = frames_processed - 1
            all_detections.extend(res["detections"])
            if res["anomaly"]:
                anomaly_scores.append(res["anomaly"]["score"])
        result = {
            "method_used": _get_detector().method_name,
            "frames_total": total,
            "frames_processed": frames_processed,
            "detections": all_detections,
            "defect_frame_ratio": round(defect_frames / max(1, frames_processed), 3),
            "anomaly_avg_score": round(float(np.mean(anomaly_scores)), 4) if anomaly_scores else None,
            "processing_ms": int((time.perf_counter() - t0) * 1000),
            "model_version": "classical-cv-1.0",
        }
        return result
    finally:
        if cap is not None:
            cap.release()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def make_annotated(img_bgr: np.ndarray, detections: list[dict]) -> bytes:
    from app.services.vision.preprocessing import encode_png

    return encode_png(annotated_overlay(img_bgr, detections))
