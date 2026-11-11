# Model Card — Surface Anomaly Autoencoder

**Version**: v1.0.0-20261110 · **Task**: unsupervised anomaly scoring ·
**Framework**: PyTorch (CPU)

## Approach
Conv autoencoder (latent 32) trained **only on clean surfaces**; anomaly score
= reconstruction MSE; threshold = clean-validation mean + 2σ.

## Measured (test, honest — `ml/artifacts/vision/ae_metrics.json`)
- threshold MSE, clean FPR, per-defect reconstruction errors and detection
  rate recorded at training time; the pipeline labels the method used
  (`autoencoder_reconstruction`) in every API response.
- Always-available fallback: classical Laplacian-statistics score
  (`classical_laplacian_stats`) when torch/artifact missing.

## Limitations
- Trained on synthetic textures; threshold transfer to real optics requires
  retraining on the target camera setup.

---

# Experiment Card — Machine Behavior Clustering

**Task**: exploratory unsupervised segmentation (KMeans k=2..6 silhouette
sweep → best k; DBSCAN eps grid) over AI4I-style engineered features.

## Measured
- Best KMeans silhouette ≈ **0.31** (see `ml/artifacts/clustering/experiments.json`)
- DBSCAN sweep reports cluster counts + noise ratios per eps.

## Usage & guardrails
Artifact `kmeans.joblib` is exposed via `behavior_segment()` and the registry
(status **staging**), explicitly documented as **not** used for production
maintenance decisions — it is an analysis lens, not a control signal.
