"""Shared autoencoder architecture for anomaly detection (train + inference)."""
from __future__ import annotations

import torch.nn as nn


class SurfaceAutoencoder(nn.Module):
    """Conv autoencoder over 64x64 grayscale surface patches."""

    def __init__(self, latent: int = 32):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, 3, stride=2, padding=1), nn.ReLU(),  # 32
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),  # 16
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),  # 8
            nn.Flatten(),
            nn.Linear(64 * 8 * 8, latent), nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent, 64 * 8 * 8), nn.ReLU(),
            nn.Unflatten(1, (64, 8, 8)),
            nn.ConvTranspose2d(64, 32, 3, stride=2, padding=1, output_padding=1), nn.ReLU(),  # 16
            nn.ConvTranspose2d(32, 16, 3, stride=2, padding=1, output_padding=1), nn.ReLU(),  # 32
            nn.ConvTranspose2d(16, 1, 3, stride=2, padding=1, output_padding=1),              # 64
            nn.Sigmoid(),
        )

    def forward(self, x):  # noqa: ANN001
        return self.decoder(self.encoder(x))
