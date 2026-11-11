from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.core.enums import InspectionKind, InspectionResult, InspectionStatus
from app.core.metrics import INSPECTIONS_TOTAL
from app.models.inspection import DetectedDefect, Inspection, InspectionImage
from app.schemas.common import Page
from app.schemas.inspection import DefectOut, InspectionDetailOut, InspectionOut
from app.services.audit import audit_log
from app.services.storage import get_storage
from app.services.vision import pipeline as vp
from app.services.vision.preprocessing import resize_max
from app.workers.tasks import process_video_inspection

router = APIRouter(prefix="/vision", tags=["vision"])

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 150 * 1024 * 1024


def _ext(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


async def _read_upload(upload: UploadFile, max_bytes: int, allowed: set[str]) -> tuple[str, bytes]:
    if _ext(upload.filename or "") not in allowed:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}",
        )
    data = await upload.read()
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds size limit of {max_bytes // (1024 * 1024)} MB",
        )
    return upload.filename or "upload", data


@router.post("/inspect", response_model=InspectionDetailOut, status_code=201)
async def inspect_image(
    request: Request,
    file: UploadFile,
    current: CurrentUserDep,
    db: DbDep,
    background: BackgroundTasks,
    machine_id: int | None = None,
    do_ocr: bool = False,
):
    """Synchronous single-image inspection (real inference, annotated output)."""
    require("run_inspection")(current)
    filename, data = await _read_upload(file, MAX_IMAGE_BYTES, IMAGE_EXTS)
    try:
        img = vp.decode_image(data)
        if img is None:
            raise ValueError("corrupt image")
        result = vp.inspect_image(img, do_ocr=do_ocr)
    except ValueError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))

    storage = get_storage()
    file_key = storage.save(data, filename, "inspections")
    annotated_key = storage.save(
        vp.make_annotated(resize_max(img), result["detections"]),
        f"annotated_{filename.rsplit('.', 1)[0]}.png",
        "inspections",
    )

    inspection = Inspection(
        org_id=current.org_id, machine_id=machine_id, kind=InspectionKind.IMAGE.value,
        filename=filename, file_key=file_key, status=InspectionStatus.COMPLETED.value,
        result=(InspectionResult.DEFECT_DETECTED.value if result["detections"] else InspectionResult.OK.value),
        defect_count=len(result["detections"]),
        avg_confidence=(sum(d["confidence"] for d in result["detections"]) / len(result["detections"]))
        if result["detections"] else None,
        method_used=result["method_used"], processing_ms=result["processing_ms"],
        model_version=result["model_version"], created_by=current.id,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(inspection)
    db.flush()
    db.add(InspectionImage(inspection_id=inspection.id, file_key=file_key,
                           width=img.shape[1], height=img.shape[0]))
    db.add(InspectionImage(inspection_id=inspection.id, file_key=annotated_key,
                           width=img.shape[1], height=img.shape[0]))
    for d in result["detections"]:
        db.add(DetectedDefect(
            inspection_id=inspection.id, org_id=current.org_id, label=d["label"],
            confidence=d["confidence"], bbox_x1=d.get("bbox_x1"), bbox_y1=d.get("bbox_y1"),
            bbox_x2=d.get("bbox_x2"), bbox_y2=d.get("bbox_y2"),
            severity=d.get("severity"), method=d.get("method"),
        ))
    audit_log(db, org_id=current.org_id, user_id=current.id, action="inspection_create",
              resource="inspection", resource_id=inspection.id,
              detail={"defects": len(result["detections"])},
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(inspection)

    INSPECTIONS_TOTAL.labels(
        kind="image", result=inspection.result or "ok", method=result["method_used"]
    ).inc()
    # Live WS event (always — not only for unlinked inspections)
    try:
        from app.api.v1.ws import notify_org

        background.add_task(notify_org, current.org_id, {
            "event": "inspection_completed", "inspection_id": inspection.id,
            "result": inspection.result,
        })
    except Exception:
        pass

    detail = _detail_out(inspection)
    detail.images = [{"file_key": file_key}, {"file_key": annotated_key, "annotated": True}]
    detail.anomaly = result["anomaly"]
    detail.ocr = result["ocr"]
    return detail


@router.post("/video", response_model=InspectionOut, status_code=202)
async def inspect_video(
    request: Request,
    file: UploadFile,
    current: CurrentUserDep,
    db: DbDep,
    background: BackgroundTasks,
    machine_id: int | None = None,
):
    """Asynchronous video inspection — returns 202 immediately; poll the detail endpoint."""
    require("run_inspection")(current)
    filename, data = await _read_upload(file, MAX_VIDEO_BYTES, VIDEO_EXTS)
    file_key = get_storage().save(data, filename, "inspections")
    inspection = Inspection(
        org_id=current.org_id, machine_id=machine_id, kind=InspectionKind.VIDEO.value,
        filename=filename, file_key=file_key, status=InspectionStatus.PENDING.value,
        created_by=current.id,
    )
    db.add(inspection)
    audit_log(db, org_id=current.org_id, user_id=current.id, action="inspection_video_queue",
              resource="inspection", resource_id=inspection.id,
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(inspection)
    background.add_task(process_video_inspection, inspection.id)
    return InspectionOut.model_validate(inspection)


@router.get("/inspections", response_model=Page[InspectionOut])
def list_inspections(
    current: CurrentUserDep, db: DbDep, page: PageParams,
    machine_id: int | None = None, result: str | None = None, kind: str | None = None,
):
    q = db.query(Inspection).filter(Inspection.org_id == current.org_id)
    if machine_id:
        q = q.filter(Inspection.machine_id == machine_id)
    if result:
        q = q.filter(Inspection.result == result)
    if kind:
        q = q.filter(Inspection.kind == kind)
    total = q.count()
    items = q.order_by(Inspection.created_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[InspectionOut](
        items=[InspectionOut.model_validate(i) for i in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


def _detail_out(insp: Inspection) -> InspectionDetailOut:
    """Build detail from the flat InspectionOut schema (avoids validating the
    selectin-loaded `images` ORM objects against a dict field)."""
    data = InspectionOut.model_validate(insp).model_dump()
    return InspectionDetailOut(
        **data,
        defects=[DefectOut.model_validate(d) for d in insp.defects],
        images=[],
    )


@router.get("/inspections/{inspection_id}", response_model=InspectionDetailOut)
def get_inspection(inspection_id: int, current: CurrentUserDep, db: DbDep):
    insp = db.query(Inspection).filter(
        Inspection.id == inspection_id, Inspection.org_id == current.org_id
    ).first()
    if not insp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inspection not found")
    detail = _detail_out(insp)
    detail.images = [
        {"file_key": img.file_key, "frame_index": img.frame_index,
         "width": img.width, "height": img.height}
        for img in insp.images
    ]
    return detail


def _load_image_bytes(db, current: CurrentUserDep, inspection_id: int, annotated: bool) -> bytes:
    insp = db.query(Inspection).filter(
        Inspection.id == inspection_id, Inspection.org_id == current.org_id
    ).first()
    if not insp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inspection not found")
    img_row = None
    for img in insp.images:
        if annotated and "annotated_" in (img.file_key or ""):
            img_row = img
            break
        if not annotated and "annotated_" not in (img.file_key or ""):
            img_row = img
            break
    if img_row is None or not img_row.file_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not stored for this inspection")
    try:
        return get_storage().open_bytes(img_row.file_key)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stored file missing")


@router.get("/inspections/{inspection_id}/image")
def get_inspection_image(inspection_id: int, current: CurrentUserDep, db: DbDep):
    data = _load_image_bytes(db, current, inspection_id, annotated=False)
    return Response(content=data, media_type="image/png")


@router.get("/inspections/{inspection_id}/annotated")
def get_inspection_annotated(inspection_id: int, current: CurrentUserDep, db: DbDep):
    data = _load_image_bytes(db, current, inspection_id, annotated=True)
    return Response(content=data, media_type="image/png")
