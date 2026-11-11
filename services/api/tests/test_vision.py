"""Vision inspection: validation, real pipeline inference, annotated output."""
from __future__ import annotations

import cv2

from app.services.vision.synth import generate_defect_image


def _png_bytes(kind="scratch", seed=7) -> bytes:
    img = generate_defect_image(kind, seed=seed)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_invalid_file_rejected(client, engineer_headers):
    r = client.post("/api/v1/vision/inspect", headers=engineer_headers,
                    files={"file": ("malware.exe", b"MZfake", "application/octet-stream")})
    assert r.status_code == 415


def test_corrupt_image_rejected(client, engineer_headers):
    r = client.post("/api/v1/vision/inspect", headers=engineer_headers,
                    files={"file": ("broken.png", b"not-an-image", "image/png")})
    assert r.status_code == 415


def test_image_inspection_full_pipeline(client, engineer_headers):
    data = _png_bytes("scratch", seed=11)
    r = client.post("/api/v1/vision/inspect?do_ocr=true", headers=engineer_headers,
                    files={"file": ("panel.png", data, "image/png")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["method_used"] in ("classical_anomaly_grid", "yolo")
    assert body["processing_ms"] is not None
    assert isinstance(body["defects"], list)
    assert body["anomaly"]["method"] in ("classical_laplacian_stats", "autoencoder_reconstruction")
    assert body["ocr"]["method"] in ("tesseract", "unavailable")


def test_annotated_image_served(client, engineer_headers):
    data = _png_bytes("dent", seed=21)
    r = client.post("/api/v1/vision/inspect", headers=engineer_headers,
                    files={"file": ("panel2.png", data, "image/png")})
    insp_id = r.json()["id"]
    r2 = client.get(f"/api/v1/vision/inspections/{insp_id}/annotated", headers=engineer_headers)
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("image/")
    assert len(r2.content) > 500


def test_inspection_list_pagination(client, engineer_headers):
    r = client.get("/api/v1/vision/inspections?page=1&page_size=5", headers=engineer_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1 and body["page_size"] == 5
    assert len(body["items"]) <= 5


def test_inspection_detail_cross_tenant_hidden(client, engineer_headers, headers2):
    data = _png_bytes("clean", seed=31)
    r = client.post("/api/v1/vision/inspect", headers=engineer_headers,
                    files={"file": ("panel3.png", data, "image/png")})
    insp_id = r.json()["id"]
    r2 = client.get(f"/api/v1/vision/inspections/{insp_id}", headers=headers2)
    assert r2.status_code == 404


def test_video_upload_async(client, engineer_headers):
    # 1-second synthetic AVI built by OpenCV
    import tempfile
    from pathlib import Path

    path = Path(tempfile.mkdtemp()) / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    for i in range(12):
        writer.write(generate_defect_image("scratch", seed=100 + i))
    writer.release()

    with open(path, "rb") as f:
        r = client.post("/api/v1/vision/video", headers=engineer_headers,
                        files={"file": ("clip.avi", f.read(), "video/x-msvideo")})
    assert r.status_code == 202, r.text
    insp_id = r.json()["id"]

    # background task runs synchronously inside TestClient — result should exist
    r2 = client.get(f"/api/v1/vision/inspections/{insp_id}", headers=engineer_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] in ("completed", "failed")
