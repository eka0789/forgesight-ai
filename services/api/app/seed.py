"""Idempotent demo seeder.

Everything created here is marked demo (`is_demo=True` on org, inspections,
predictions, documents) and surfaced in the UI so demo data is never confused
with production data. Demo sensor data is SYNTHETIC (deterministic generator).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.inspection import DetectedDefect, Inspection
from app.models.knowledge import Document, DocumentChunk
from app.models.machine import Machine, SensorReading
from app.models.maintenance import MaintenancePrediction, MaintenanceRequest
from app.models.organization import Organization
from app.models.user import User
from app.services.knowledge.chunking import chunk_document
from app.services.knowledge.embeddings import get_embedding_provider
from app.services.mlops.registry import register_all
from app.services.pdm import inference as pdm
from app.services.vision import pipeline as vp
from app.services.vision.synth import generate_defect_image

logger = logging.getLogger(__name__)

DEMO_ORG_SLUG = "nusantara-manufacturing-demo"
DEMO_ADMIN_EMAIL = "admin@demo.forgesight.ai"
DEMO_PASSWORD = "Demo1234!"  # demo-only credential, documented

MACHINES = [
    ("CNC-01", "CNC Milling Machine", "cnc", "Hall A"),
    ("CNC-02", "CNC Lathe", "cnc", "Hall A"),
    ("INJ-01", "Injection Molder 300T", "injection", "Hall B"),
    ("CONV-01", "Main Conveyor Line 1", "conveyor", "Hall B"),
    ("PRES-01", "Hydraulic Press 120T", "press", "Hall C"),
]

DEMO_DOCS = [
    ("CNC-01 Maintenance SOP", """Standard Operating Procedure — CNC-01 Maintenance.
Daily checks: verify lubrication levels, inspect spindle runout (max 0.005mm), check hydraulic pressure at 120 bar.
Tool wear must not exceed 240 minutes before replacement. Replace the cutting tool when wear exceeds 200 minutes.
Cooling system: coolant temperature must stay between 22 and 28 degrees Celsius. If the temperature delta between
process and ambient exceeds 8.6K while spindle speed is below 1380 rpm, stop the machine and inspect the chiller.
Vibration alarm threshold: 4.5 mm/s RMS at spindle bearing housing.
Monthly: replace air filter, verify guideway geometry, calibrate probes."""),
    ("Quality Inspection Manual", """Surface Quality Inspection Manual.
Acceptable products must be free of scratches deeper than 0.1mm, staining, and dents on Class-A surfaces.
Inspection procedure: clean the surface, use consistent lighting at 45 degrees, capture image at 2MP minimum.
A defect is classified critical when it affects assembly fit; high when visible without magnification.
Confidence threshold for automated rejection: 0.75. Products between 0.5 and 0.75 require manual review.
OCR of production labels must match the work order; mismatched labels are quarantined."""),
    ("Predictive Maintenance Policy", """Predictive Maintenance Policy.
Failure risk levels: low below 20 percent failure probability, medium 20-50, high 50-80, critical above 80.
Machines with high or critical risk must generate a maintenance request and be reviewed within 24 hours.
Remaining Useful Life below 168 hours triggers expedited parts procurement.
Power draw outside 3500-9000W indicates power failure risk; inspect the spindle drive.
Overstrain is defined as tool wear multiplied by torque above 11000 minNm for L-type tools."""),
]


def seed_demo() -> dict:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
        if org:
            logger.info("demo seed: already present (org id=%s)", org.id)
            return {"status": "already_present", "org_id": org.id}

        org = Organization(name="Nusantara Manufacturing (Demo)", slug=DEMO_ORG_SLUG, is_demo=True)
        db.add(org)
        db.flush()

        admin = User(
            org_id=org.id, email=DEMO_ADMIN_EMAIL, hashed_password=hash_password(DEMO_PASSWORD),
            full_name="Demo Admin", role="owner",
        )
        engineer = User(
            org_id=org.id, email="engineer@demo.forgesight.ai", hashed_password=hash_password(DEMO_PASSWORD),
            full_name="Demo Engineer", role="engineer",
        )
        db.add_all([admin, engineer])
        db.flush()

        rng = np.random.default_rng(42)
        now = datetime.now(timezone.utc)
        machines: list[Machine] = []
        for i, (code, name, mtype, loc) in enumerate(MACHINES):
            m = Machine(org_id=org.id, code=code, name=name, machine_type=mtype, location=loc,
                        status=["healthy", "healthy", "warning", "healthy", "critical"][i])
            db.add(m)
            machines.append(m)
        db.flush()

        # 30 days of hourly synthetic readings (AI4I-style)
        for m in machines:
            skew = {"healthy": 0.0, "warning": 0.35, "critical": 0.85}[m.status]
            n = 24 * 30
            air = rng.normal(300, 2, n)
            process = air + rng.normal(10 - 3 * skew, 1.2, n)
            torque = rng.normal(40 + 12 * skew, 10, n).clip(2)
            speed = (1500 - 5 * (torque - 40) + rng.normal(0, 120, n)).clip(1100, 2400)
            wear = rng.normal(100 + 90 * skew, 30, n).clip(0, 265)
            vib = rng.normal(1.5 + 1.8 * skew, 0.5, n).clip(0.1, 8)
            ts0 = now - timedelta(hours=n)
            for j in range(n):
                db.add(SensorReading(
                    machine_id=m.id, ts=ts0 + timedelta(hours=j),
                    air_temperature=float(air[j]), process_temperature=float(process[j]),
                    rotational_speed=float(speed[j]), torque=float(torque[j]),
                    tool_wear=float(wear[j]), vibration=float(vib[j]),
                ))

        # Real vision inspections on synthetic images (real pipeline inference).
        # zlib.crc32 → deterministic seeds across processes (hash() is randomized).
        import zlib

        for kind, label in (("scratch", "scratch"), ("clean", "clean"), ("dent", "dent")):
            img = generate_defect_image(kind, seed=zlib.crc32(kind.encode()) % 10_000)
            result = vp.inspect_image(img)
            insp = Inspection(
                org_id=org.id, machine_id=machines[0].id, kind="image",
                filename=f"demo_{kind}.png", file_key=None, status="completed",
                result="defect_detected" if result["detections"] else "ok",
                defect_count=len(result["detections"]),
                avg_confidence=(sum(d["confidence"] for d in result["detections"]) / len(result["detections"]))
                if result["detections"] else None,
                method_used=result["method_used"], processing_ms=result["processing_ms"],
                model_version=result["model_version"], is_demo=True, created_by=admin.id,
                completed_at=now,
            )
            db.add(insp)
            db.flush()
            for d in result["detections"]:
                db.add(DetectedDefect(
                    inspection_id=insp.id, org_id=org.id, label=label if result["detections"] else d["label"],
                    confidence=d["confidence"], bbox_x1=d.get("bbox_x1"), bbox_y1=d.get("bbox_y1"),
                    bbox_x2=d.get("bbox_x2"), bbox_y2=d.get("bbox_y2"), severity=d.get("severity"),
                    method=d.get("method"),
                ))

        # Real PDM predictions per machine (model artifacts if present)
        for m in machines:
            latest = db.query(SensorReading).filter(SensorReading.machine_id == m.id).order_by(SensorReading.ts.desc()).first()
            if not latest:
                continue
            payload = {
                "air_temperature": latest.air_temperature, "process_temperature": latest.process_temperature,
                "rotational_speed": latest.rotational_speed, "torque": latest.torque,
                "tool_wear": latest.tool_wear, "vibration": latest.vibration,
            }
            result = pdm.predict_failure(payload)
            try:
                rul = pdm.predict_rul(payload)["rul_hours"]
            except Exception:
                rul = None
            db.add(MaintenancePrediction(
                org_id=org.id, machine_id=m.id, model_version=result["model_version"] or "unknown",
                failure_probability=result["failure_probability"], risk_level=result["risk_level"],
                health_score=pdm.health_score(result, rul), rul_hours=rul,
                predicted_modes=result["predicted_modes"], recommendations=result["recommendations"],
                input_snapshot=payload, is_demo=True, created_by=engineer.id,
            ))

        db.add_all([
            MaintenanceRequest(org_id=org.id, machine_id=machines[4].id,
                               title="Hydraulic press seal inspection",
                               description="Critical risk from PDM model; inspect seals and lubrication.",
                               priority="urgent", status="open", source="system", created_by=engineer.id),
            MaintenanceRequest(org_id=org.id, machine_id=machines[2].id,
                               title="Cooling system check — injection molder",
                               priority="medium", status="open", source="manual", created_by=engineer.id),
        ])

        # Real document ingestion (embeddings computed now)
        provider = get_embedding_provider()
        for title, text in DEMO_DOCS:
            doc = Document(org_id=org.id, title=title, filename=f"{title}.txt", mime="text/plain",
                           size_bytes=len(text.encode()), status="indexed", is_demo=True,
                           created_by=admin.id, chunk_count=0)
            db.add(doc)
            db.flush()
            chunks = chunk_document(text)
            vectors = provider.embed_batch([c["content"] for c in chunks])
            for chunk, vec in zip(chunks, vectors):
                db.add(DocumentChunk(org_id=org.id, document_id=doc.id, chunk_index=chunk["index"],
                                     content=chunk["content"], page_number=chunk["page_number"],
                                     tokens=chunk["tokens"], embedding=vec))
            doc.chunk_count = len(chunks)

        register_all(db, created_by="demo-seed")
        db.commit()
        logger.info("demo seed complete: org=%s admin=%s", org.id, DEMO_ADMIN_EMAIL)
        return {"status": "created", "org_id": org.id, "admin_email": DEMO_ADMIN_EMAIL,
                "password": DEMO_PASSWORD}
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
