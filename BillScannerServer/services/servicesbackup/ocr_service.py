import os
import cv2
from typing import List, Dict

from paddleocr import PaddleOCR
from receipt_parser import parse_receipt as advanced_parser

# ---------------- CONFIG ---------------- #

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

DEBUG = True
_OCR_ENGINE = None


# ---------------- OCR INIT ---------------- #

def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    _OCR_ENGINE = PaddleOCR(
        lang="en",
        use_angle_cls=True,
    )
    return _OCR_ENGINE


# ---------------- IMAGE PREPROCESS ---------------- #

def _resize_if_needed(image_path: str):
    img = cv2.imread(image_path)

    if img is None:
        return

    h, w = img.shape[:2]
    max_side = max(h, w)

    if max_side > 1200:
        scale = 1200 / max_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        cv2.imwrite(image_path, img)
        print(f"[INFO] Image resized to {img.shape}")


# ---------------- OCR ---------------- #

def extract_text(image_path: str) -> List[str]:
    ocr = _get_ocr_engine()

    _resize_if_needed(image_path)

    result = ocr.ocr(image_path)

    print("\n========== OCR RAW ==========")
    print(result)

    lines = []
    print("\n========== OCR OUTPUT ==========")

    if not result or len(result) == 0:
        print("❌ Empty OCR result")
        return []

    if result[0] is None or len(result[0]) == 0:
        print("❌ No text detected")
        return []

    for line in result[0]:
        try:
            text = line[1][0]
            conf = line[1][1]
        except (IndexError, TypeError):
            print("⚠️ Skipping malformed line:", line)
            continue

        print(f"[OCR] {text} (conf={conf:.2f})")

        if conf > 0.3:
            lines.append(text)

    print("================================\n")

    return lines


# ---------------- MAIN PIPELINE ---------------- #

def process_bill(image_path: str) -> Dict:
    print("\n🚀 Processing bill:", image_path)

    try:
        lines = extract_text(image_path)

        if not lines:
            return {
                "items": [],
                "total_amount": 0,
                "error": "No text detected"
            }

        result = advanced_parser(lines)

        print("\n✅ FINAL RESULT")
        print(result)
        print("\n")

        return result

    except Exception as e:
        print("❌ Bill processing failed:", str(e))

        return {
            "items": [],
            "total_amount": 0,
            "error": str(e)
        }