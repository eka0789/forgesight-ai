"""OCR for production labels (guarded: requires the tesseract binary)."""
from __future__ import annotations


def ocr_text(img_bgr) -> dict:
    try:
        import cv2
        import pytesseract
        from PIL import Image  # noqa: F401  (pytesseract requires it)

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        text = pytesseract.image_to_string(gray, config="--psm 6")
        return {"text": text.strip(), "method": "tesseract", "available": True}
    except Exception:
        return {
            "text": "",
            "method": "unavailable",
            "available": False,
            "note": "OCR requires the tesseract binary + pytesseract package; not installed on this host.",
        }
