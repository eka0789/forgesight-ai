"""Anomaly scoring layer.

1. Autoencoder reconstruction error (PyTorch, trained on 'clean' synthetic
   surfaces) when artifact available.
2. Always-available classical image-statistics score (real method, labeled).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings


class AutoencoderAnomaly:
    def __init__(self):
        self._torch = None
        self._model = None
        self.threshold = None
        self.version = None
        self.available = False

    def load(self) -> None:
        if self.available:
            return
        path = Path(settings.resolved_artifacts_dir) / "vision" / "anomaly_ae.pt"
        if not path.exists():
            return
        try:
            import torch

            from app.services.vision.ae_model import SurfaceAutoencoder

            if SurfaceAutoencoder is None:  # torch absent → classical fallback path
                return

            self._torch = torch
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            model = SurfaceAutoencoder(latent=ckpt.get("latent", 32))
            model.load_state_dict(ckpt["state_dict"])
            model.eval()
            self._model = model
            self.threshold = ckpt.get("threshold")
            self.version = ckpt.get("version")
            self.available = True
        except Exception:
            self.available = False

    def score(self, img_bgr: np.ndarray) -> dict | None:
        self.load()
        if not self.available:
            return None
        torch = self._torch
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64)).astype(np.float32) / 255.0
        t = torch.tensor(resized)[None, None, :, :]
        with torch.no_grad():
            recon = self._model(t)
        err = float(((recon - t) ** 2).mean())
        is_anom = (self.threshold is not None and err > self.threshold)
        return {
            "score": round(err, 6),
            "threshold": self.threshold,
            "is_anomalous": bool(is_anom),
            "version": self.version,
            "method": "autoencoder_reconstruction",
        }


def classical_score(img_bgr: np.ndarray) -> dict:
    """Image-statistics anomaly heuristic (always available, clearly labeled)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    # Healthy surfaces: low local variance of texture residual. Distortions
    # (scratches/stains) inflate kurtosis of the Laplacian response.
    kurt = float(((lap - lap.mean()) ** 4).mean() / (max(lap.var(), 1e-6) ** 2) - 3.0)
    score = float(np.clip(kurt / 20.0, 0, 1))
    return {
        "score": round(score, 4),
        "threshold": 0.5,
        "is_anomalous": score >= 0.5,
        "method": "classical_laplacian_stats",
    }


ae_anomaly = AutoencoderAnomaly()
