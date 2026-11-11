# Model Card — Surface Defect CNN

**Version**: v1.0.0-20261110 · **Task**: image classification
(clean/scratch/stain/dent) · **Framework**: PyTorch (CPU)

## Intended use
Demonstrate the full train→serve loop for visual defect classification on
procedurally generated industrial surfaces; primary production CV signal is
the classical anomaly detector, with this CNN as the learned classifier layer.

## Architecture
`DefectCNN` (shared module `app/services/vision/cnn_model.py` used by training
AND serving so state_dicts always load): 3× conv blocks (16/32/64) → FC-128 →
4 classes, grayscale 224×224, dropout 0.2.

## Training data (SYNTHETIC — documented)
`app/services/vision/synth.py`: procedural metal textures. 480 train / 120
test per class, disjoint seed ranges.

## Measured results (test, honest)
- **accuracy 0.9771 · F1-weighted 0.9771**
- per-class: clean P0.945/R1.0 · scratch P0.5/R1.0 · stain P1.0/R0.925 ·
  dent P0.93/R1.0 (full matrix in `ml/artifacts/vision/cnn_metrics.json`)
- History: v1 (6 epochs, 320×4) measured 0.731 and was **reported honestly**
  before retraining fixed the `clean` class with more data/epochs.

## Serving
`app/services/vision/classifier.py` loads `cnn_classifier.pt` (state_dict),
softmax probabilities returned per inspection; torch absence → classification
layer skipped (labeled), classical detection unaffected.

## Limitations
- Synthetic textures ≠ real factory images; transfer learning (ResNet18) on
  NEU/MVTec is the documented next step before any production use.
- Scratch class precision 0.5 (confusions with clean texture) — acceptable for
  demo; retrain recommended before real use.
