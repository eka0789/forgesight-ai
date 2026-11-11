"""Defect-class CNN training on SYNTHETIC surface images (clean/scratch/stain/dent).

Requires torch. Trains a small CNN, reports honest test metrics, saves a
state_dict checkpoint consumable by the API classifier (shared architecture
module). The dataset is procedurally generated and clearly labeled synthetic.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from ml.training.common import ARTIFACTS_DIR, report

N_PER_CLASS_TRAIN = 480
N_PER_CLASS_TEST = 120
EPOCHS = 14
BATCH = 64
SEED = 42


def main() -> None:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        print("[skip] torch not installed — CNN training skipped. Classical CV paths remain available.")
        doc = {"status": "skipped", "reason": "torch not installed", "version": "not-trained"}
        (ARTIFACTS_DIR / "vision" / "cnn_metrics.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return

    import cv2
    import numpy as np
    from app.services.vision.cnn_model import DefectCNN
    from app.services.vision.synth import CLASSES, generate_defect_image

    torch.manual_seed(SEED)

    def make_split(n_per_class: int, offset: int) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = [], []
        for ci, cls in enumerate(CLASSES):
            for j in range(n_per_class):
                img = generate_defect_image(cls, seed=offset + ci * 10_000 + j)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
                xs.append(gray)
                ys.append(ci)
        x = np.stack(xs)[:, None, :, :]  # (N,1,H,W)
        return torch.tensor(x, dtype=torch.float32), torch.tensor(ys, dtype=torch.long)

    print("generating synthetic dataset...")
    x_train, y_train = make_split(N_PER_CLASS_TRAIN, 0)
    x_test, y_test = make_split(N_PER_CLASS_TEST, 900_000)
    print(f"train={len(y_train)} test={len(y_test)} classes={CLASSES}")

    train_loader = DataLoader(TensorDataset(x_train, y_train), batch_size=BATCH, shuffle=True)
    model = DefectCNN(num_classes=len(CLASSES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0
        for xb, yb in train_loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            total_loss += float(loss)
        model.eval()
        with torch.no_grad():
            logits = model(x_test)
            acc = float((logits.argmax(1) == y_test).float().mean())
        print(f"epoch {epoch + 1}/{EPOCHS} loss={total_loss / max(1, len(train_loader)):.4f} test_acc={acc:.4f}")

    with torch.no_grad():
        preds = model(x_test).argmax(1).numpy()
    y_np = y_test.numpy()
    prec, rec, _, _ = precision_recall_fscore_support(y_np, preds, labels=range(len(CLASSES)), zero_division=0)
    metrics = {
        "accuracy": round(float(accuracy_score(y_np, preds)), 4),
        "f1_weighted": round(float(f1_score(y_np, preds, average="weighted")), 4),
        "per_class": {c: {"precision": round(float(p), 3), "recall": round(float(r), 3)}
                      for c, p, r in zip(CLASSES, prec, rec)},
        "confusion_matrix": __import__("sklearn.metrics", fromlist=["confusion_matrix"])
        .confusion_matrix(y_np, preds).tolist(),
    }

    ckpt = {
        "state_dict": model.state_dict(),
        "classes": CLASSES,
        "version": "v1.0.0-" + datetime.now(UTC).strftime("%Y%m%d"),
        "metrics": metrics,
    }
    out = ARTIFACTS_DIR / "vision" / "cnn_classifier.pt"
    torch.save(ckpt, out)
    doc = {"status": "trained", "version": ckpt["version"], "metrics": metrics,
           "params": {"epochs": EPOCHS, "batch": BATCH, "train_images": len(y_train),
                      "test_images": len(y_test), "architecture": "DefectCNN-3conv",
                      "dataset": "synthetic_procedural (clean/scratch/stain/dent)"},
           "splits": {"test": metrics}}
    (ARTIFACTS_DIR / "vision" / "cnn_metrics.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report("defect CNN", doc)


if __name__ == "__main__":
    main()
