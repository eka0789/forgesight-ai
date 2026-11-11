"""Exports the OpenAPI schema to shared/contracts/openapi.json (frontend/CI use)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app.main import create_app

out = REPO / "shared" / "contracts"
out.mkdir(parents=True, exist_ok=True)
schema = create_app().openapi()
(out / "openapi.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
print(f"openapi.json written ({len(json.dumps(schema))} bytes) → {out}")
