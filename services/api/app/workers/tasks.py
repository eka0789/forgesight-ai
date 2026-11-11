"""Background task functions (FastAPI BackgroundTasks runner).

Long-running work (video inference, document ingestion) runs as detached
tasks with their own DB sessions. The architecture keeps a task registry so a
dedicated RQ/Celery worker can adopt the same functions without changes.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.inspection import DetectedDefect, Inspection, InspectionImage
from app.models.knowledge import Document, DocumentChunk
from app.services.knowledge.chunking import chunk_document
from app.services.knowledge.embeddings import get_embedding_provider
from app.services.knowledge.extract import extract_text
from app.services.vision import pipeline as vp


def process_video_inspection(inspection_id: int) -> None:
    db = SessionLocal()
    try:
        inspection = db.get(Inspection, inspection_id)
        if inspection is None:
            return
        inspection.status = "processing"
        db.commit()
        from app.services.storage import get_storage

        data = get_storage().open_bytes(inspection.file_key)
        result = vp.inspect_video_bytes(data, inspection.filename)

        inspection.status = "completed"
        inspection.method_used = result["method_used"]
        inspection.processing_ms = result["processing_ms"]
        inspection.model_version = result["model_version"]
        inspection.defect_count = len(result["detections"])
        inspection.result = "defect_detected" if result["detections"] else "ok"
        if result["detections"]:
            confs = [d["confidence"] for d in result["detections"]]
            inspection.avg_confidence = sum(confs) / len(confs)
        for d in result["detections"]:
            db.add(DetectedDefect(
                inspection_id=inspection.id, org_id=inspection.org_id, label=d["label"],
                confidence=d["confidence"], bbox_x1=d.get("bbox_x1"), bbox_y1=d.get("bbox_y1"),
                bbox_x2=d.get("bbox_x2"), bbox_y2=d.get("bbox_y2"), severity=d.get("severity"),
                method=d.get("method"),
            ))
        db.add(InspectionImage(
            inspection_id=inspection.id, file_key=inspection.file_key or "",
            frame_index=None, width=None, height=None,
        ))
        inspection.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        inspection = db.get(Inspection, inspection_id)
        if inspection:
            inspection.status = "failed"
            inspection.error = f"{exc.__class__.__name__}: {exc}"
            db.commit()
    finally:
        db.close()


def ingest_document(document_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        doc.status = "processing"
        db.commit()

        if doc.file_key:
            from app.services.storage import get_storage

            data = get_storage().open_bytes(doc.file_key)
        else:
            data = (doc.error or "").encode("utf-8")

        extracted = extract_text(doc.filename, data, doc.mime)
        chunks = chunk_document(extracted["text"])

        provider = get_embedding_provider()
        vectors = provider.embed_batch([c["content"] for c in chunks])

        for chunk, vec in zip(chunks, vectors):
            db.add(DocumentChunk(
                org_id=doc.org_id, document_id=doc.id, chunk_index=chunk["index"],
                content=chunk["content"], page_number=chunk["page_number"],
                tokens=chunk["tokens"], embedding=vec,
            ))

        doc.status = "indexed"
        doc.page_count = extracted["pages"]
        doc.chunk_count = len(chunks)
        doc.mime = doc.mime or f"application/{extracted['kind']}"
        db.commit()
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            doc.error = f"{exc.__class__.__name__}: {exc} | {traceback.format_exc()[-400:]}"
            db.commit()
    finally:
        db.close()
