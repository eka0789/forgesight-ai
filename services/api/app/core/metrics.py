"""Prometheus metrics registry."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUEST_LATENCY = Histogram(
    "fsg_http_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

INSPECTIONS_TOTAL = Counter(
    "fsg_inspections_total",
    "Total vision inspections",
    ["kind", "result", "method"],
)

PREDICTIONS_TOTAL = Counter(
    "fsg_pdm_predictions_total",
    "Predictive-maintenance predictions",
    ["risk_level"],
)

MODEL_INFERENCE_LATENCY = Histogram(
    "fsg_model_inference_latency_seconds",
    "Model inference latency",
    ["model"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
)

ACTIVE_WS_CONNECTIONS = Gauge("fsg_ws_connections", "Active websocket connections")

APP_INFO = Gauge(
    "fsg_app_info", "Build info", ["version", "env"]
)
