"""Image classification layer.

1. PyTorch CNN trained by ml/training/train_vision_classifier.py when artifact
   + torch are available.
2. Honest fallback: classification unavailable (None) — classical detector
   results still stand.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.core.config import settings
from app.services.vision.cnn_model import INPUT_SIZE
from app.services.vision.synth import CLASSES


class CnnClassifier:
    def __init__(self):
        self._torch = None
        self._model = None
        self.classes: list[str] = list(CLASSES)
        self.version: str | None = None
        self.available = False

    def load(self) -> None:
        if self.available:
            return
        path = Path(settings.resolved_artifacts_dir) / "vision" / "cnn_classifier.pt"
        if not path.exists():
            return
        try:
            import torch

            from app.services.vision.cnn_model import DefectCNN

            if DefectCNN is None:  # torch absent → classical fallback path
                return

            self._torch = torch
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            model = DefectCNN(num_classes=len(ckpt.get("classes", self.classes)))
            model.load_state_dict(ckpt["state_dict"])
            model.eval()
            self._model = model
            self.classes = ckpt.get("classes", self.classes)
            self.version = ckpt.get("version")
            self.available = True
        except Exception:
            self.available = False

    def predict(self, img_bgr: np.ndarray) -> dict | None:
        self.load()
        if not self.available:
            return None
        torch = self._torch
        import cv2

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (INPUT_SIZE, INPUT_SIZE)).astype(np.float32) / 255.0
        tensor = torch.tensor(resized)[None, None, :, :]
        with torch.no_grad():
            probs = torch.softmax(self._model(tensor)[0], dim=0)
        idx = int(probs.argmax())
        return {
            "label": self.classes[idx],
            "confidence": round(float(probs[idx]), 4),
            "probs": {c: round(float(p), 4) for c, p in zip(self.classes, probs)},
            "version": self.version,
        }


classifier = CnnClassifier()
