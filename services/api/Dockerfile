# ForgeSight AI — API service image (CPU inference).
# Heavy optional ML stack (torch/ultralytics) is included so CNN/YOLO paths
# work out of the box in Compose; keep this image for CPU deployments.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Minimal OS deps; tesseract is optional (OCR degrades gracefully without it)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/api/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY services/api/requirements-ml.txt /app/requirements-ml.txt
RUN pip install -r requirements-ml.txt || echo "[build] optional ML stack skipped"

# Application + model artifacts (baked for reproducible inference)
COPY services/api/app /app/app
COPY services/api/alembic /app/alembic
COPY services/api/alembic.ini /app/alembic.ini
COPY ml/artifacts /app/ml/artifacts

ENV ARTIFACTS_DIR=/app/ml/artifacts \
    STORAGE_DIR=/data/storage

# Non-root runtime user
RUN useradd -m -u 10001 fsg && mkdir -p /data/storage && chown -R fsg:fsg /data /app
USER fsg

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
