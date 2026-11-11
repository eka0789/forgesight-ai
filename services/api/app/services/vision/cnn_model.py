"""Shared CNN architecture used by both training (ml/training) and inference
(API) so saved state_dicts always load cleanly."""
from __future__ import annotations

import torch.nn as nn

INPUT_SIZE = 224


class DefectCNN(nn.Module):
    """Small grayscale CNN for synthetic surface-defect classification."""

    def __init__(self, num_classes: int = 4):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # 112
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 56
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 28
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 28 * 28, 128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):  # noqa: ANN001
        return self.classifier(self.features(x))
