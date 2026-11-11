"""Autoencoder anomaly detection training on SYNTHETIC 'clean' surfaces.

Trains a conv autoencoder on clean images only, sets the anomaly threshold at
mean + 2σ of clean validation reconstruction error, and reports honest
detection accuracy on defect classes. Requires torch.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from ml.training.common import ARTIFACTS_DIR, report

N_TRAIN = 320
N_VAL = 80
N_DEFECT_TEST = 40  # per defect class
EPOCHS = 8
BATCH = 64
SEED = 42


def main() -> None:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        print("[skip] torch not installed — AE anomaly training skipped.")
        (ARTIFACTS_DIR / "vision" / "ae_metrics.json").write_text(
            json.dumps({"status": "skipped", "reason": "torch not installed"}, indent=2),
            encoding="utf-8",
        )
        return

    import cv2
    import numpy as np
    from app.services.vision.ae_model import SurfaceAutoencoder
    from app.services.vision.synth import CLASSES, generate_defect_image

    torch.manual_seed(SEED)
    SIZE = 64

    def to_tensors(kinds: list[str], n_per: int, offset: int):
        xs = []
        for kind in kinds:
            for j in range(n_per):
                img = generate_defect_image(kind, seed=offset + hash(kind) % 7000 + j)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (SIZE, SIZE)).astype(np.float32) / 255.0
                xs.append(gray)
        x = np.stack(xs)[:, None, :, :]
        return torch.tensor(x, dtype=torch.float32)

    x_train = to_tensors(["clean"], N_TRAIN, 0)
    x_val = to_tensors(["clean"], N_VAL, 500_000)
    loader = DataLoader(TensorDataset(x_train), batch_size=BATCH, shuffle=True)

    model = SurfaceAutoencoder(latent=32)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    def recon_errors(x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            recon = model(x)
            return ((recon - x) ** 2).mean(dim=(1, 2, 3))

    for epoch in range(EPOCHS):
        model.train()
        total = 0.0
        for (xb,) in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), xb)
            loss.backward()
            opt.step()
            total += float(loss)
        print(f"epoch {epoch + 1}/{EPOCHS} recon_loss={total / max(1, len(loader)):.6f}")

    val_err = recon_errors(x_val).numpy()
    threshold = float(val_err.mean() + 2 * val_err.std())
    print(f"threshold (clean mean+2σ) = {threshold:.6f}")

    defect_errs: dict[str, list[float]] = {}
    detected = 0
    total_defect = 0
    for cls in [c for c in CLASSES if c != "clean"]:
        x_def = to_tensors([cls], N_DEFECT_TEST, 800_000)
        errs = recon_errors(x_def).numpy()
        defect_errs[cls] = round(float(errs.mean()), 6)
        detected += int((errs > threshold).sum())
        total_defect += len(errs)

    clean_fpr = float((val_err > threshold).mean())
    metrics = {
        "threshold_mse": round(threshold, 6),
        "clean_val_error_mean": round(float(val_err.mean()), 6),
        "clean_false_positive_rate": round(clean_fpr, 4),
        "defect_detection_rate": round(detected / max(1, total_defect), 4),
        "defect_recon_error_mean": defect_errs,
    }

    ckpt = {
        "state_dict": model.state_dict(),
        "latent": 32,
        "threshold": threshold,
        "version": "v1.0.0-" + datetime.now(UTC).strftime("%Y%m%d"),
        "metrics": metrics,
    }
    torch.save(ckpt, ARTIFACTS_DIR / "vision" / "anomaly_ae.pt")
    doc = {"status": "trained", "version": ckpt["version"], "metrics": metrics,
           "params": {"epochs": EPOCHS, "train_clean_images": N_TRAIN,
                      "dataset": "synthetic_procedural", "input": "64x64 grayscale"},
           "splits": {"test": metrics}}
    (ARTIFACTS_DIR / "vision" / "ae_metrics.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report("anomaly autoencoder", doc)


if __name__ == "__main__":
    main()
