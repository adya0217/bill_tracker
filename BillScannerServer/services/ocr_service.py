"""
OCR for bill images: preprocess → PaddleOCR → text lines and optional token geometry.

- ``extract_text`` / ``extract_text_payload``: OCR only (used by the API upload flow;
  parsing and optional ``RECEIPT_LLM_MODE`` live in ``receipt_parser``).
- ``process_bill``: one-shot OCR → ``llm_service`` when ``USE_LLM_PROCESS_BILL`` in ``.env``
  else heuristic ``parse_receipt``. Prefer the upload API for normal bill ingestion.
"""

import os
import cv2
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings
from paddleocr import PaddleOCR

_cfg = get_settings()
os.environ.setdefault(
    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK",
    "True" if _cfg.paddle_pdx_disable_model_source_check else "False",
)

_OCR_ENGINE: Optional[PaddleOCR] = None


# ──────────────────────────────────────────────
# OCR ENGINE
# ──────────────────────────────────────────────

def _get_ocr_engine() -> PaddleOCR:
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    print("[ocr_service] Initialising PaddleOCR engine …")
    _OCR_ENGINE = PaddleOCR(
        lang="en",
        use_angle_cls=True,
        # Suppress verbose paddle logs when DEBUG=False
        
    )
    print("[ocr_service] PaddleOCR ready ✓")
    return _OCR_ENGINE


# ──────────────────────────────────────────────
# IMAGE PRE-PROCESSING
# ──────────────────────────────────────────────

def _preprocess_image(image_path: str) -> None:
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"[preprocess] ⚠️  Cannot read image at '{image_path}'")
        return

    h, w = img.shape[:2]
    max_side = max(h, w)
    print(f"[preprocess] Original size: {w}×{h}  (max_side={max_side})")

    # ── resize
    max_allowed = get_settings().ocr_preprocess_max_side
    if max_side > max_allowed:
        scale = max_allowed / max_side
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"[preprocess] Resized → {new_w}×{new_h}")
    else:
        print("[preprocess] No resize needed")

    # ── optional contrast boost for faded thermal receipts
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray.mean())
    print(f"[preprocess] Mean brightness: {mean_brightness:.1f}")

    if mean_brightness > 200:
        # Very bright / washed-out → CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        print("[preprocess] Applied CLAHE (image was too bright)")

    cv2.imwrite(image_path, img)
    print(f"[preprocess] Saved preprocessed image → '{image_path}'")


# ──────────────────────────────────────────────
# OCR
# ──────────────────────────────────────────────


def _polygon_to_bbox(poly: Any) -> Optional[Tuple[float, float, float, float]]:
    """
    Convert OCR polygon to axis-aligned bbox: (x0, y0, x1, y1).
    """
    try:
        if poly is None:
            return None
        points = []
        for p in poly:
            if p is None or len(p) < 2:
                continue
            points.append((float(p[0]), float(p[1])))
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _iter_ocr_detections(result: Any):
  
    if not result:
        return

    # PaddleOCR v3 often returns list[dict] with rec_texts/rec_scores
    first = result[0] if isinstance(result, list) and result else None
    if isinstance(first, dict):
        rec_texts = first.get("rec_texts") or []
        rec_scores = first.get("rec_scores") or []
        for idx, text in enumerate(rec_texts):
            score = rec_scores[idx] if idx < len(rec_scores) else 1.0
            try:
                conf = float(score)
            except (TypeError, ValueError):
                conf = 0.0
            yield {
                "text": str(text),
                "conf": conf,
                "poly": None,
            }
        return

    # PaddleOCR v2 legacy format
    if isinstance(first, list):
        for det in first:
            if not isinstance(det, (list, tuple)) or len(det) < 2:
                continue
            payload = det[1]
            if not isinstance(payload, (list, tuple)) or len(payload) < 2:
                continue
            text = str(payload[0])
            try:
                conf = float(payload[1])
            except (TypeError, ValueError):
                conf = 0.0
            poly = det[0] if len(det) > 0 else None
            yield {
                "text": text,
                "conf": conf,
                "poly": poly,
            }


def _iter_ocr_detections_v3_with_poly(result: Any):
    """Yield PaddleOCR v3 dict detections with polygon geometry when available."""
    if not result or not isinstance(result, list):
        return
    first = result[0]
    if not isinstance(first, dict):
        return
    rec_texts = first.get("rec_texts") or []
    rec_scores = first.get("rec_scores") or []
    rec_polys = first.get("rec_polys") or first.get("dt_polys") or []
    for idx, text in enumerate(rec_texts):
        score = rec_scores[idx] if idx < len(rec_scores) else 1.0
        poly = rec_polys[idx] if idx < len(rec_polys) else None
        try:
            conf = float(score)
        except (TypeError, ValueError):
            conf = 0.0
        yield {
            "text": str(text),
            "conf": conf,
            "poly": poly,
        }


def extract_text_payload(image_path: str) -> Dict[str, Any]:
    """
    Run PaddleOCR on image and return:
        {
            "lines": [str, ...],
            "tokens": [
                {"text","conf","x0","y0","x1","y1","cx","cy","w","h","idx"}, ...
            ]
        }
    """
    print(f"\n{'='*50}")
    print(f"[extract_text] Processing: '{image_path}'")
    print(f"{'='*50}")

    ocr = _get_ocr_engine()
    _preprocess_image(image_path)

    print("[extract_text] Running OCR …")
    result = ocr.ocr(image_path)

    try:
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                print(
                    "[extract_text] OCR payload keys:",
                    sorted(list(first.keys()))
                )
    except Exception:
        pass

    lines: List[str] = []
    tokens: List[Dict[str, Any]] = []

    if not result:
        print("[extract_text] ❌ OCR returned None/empty")
        return {"lines": lines, "tokens": tokens}

    raw_count = 0
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            raw_count = len(first.get("rec_texts") or [])
        elif isinstance(first, list):
            raw_count = len(first)
    print(f"[extract_text] {raw_count} raw detections")

    # Prefer geometry-rich iterator for v3 responses.
    detections = list(_iter_ocr_detections_v3_with_poly(result))
    if not detections:
        detections = list(_iter_ocr_detections(result))

    min_confidence = float(get_settings().ocr_min_confidence)

    for idx, det in enumerate(detections):
        text = (det.get("text") or "").strip()
        conf = float(det.get("conf") or 0.0)
        poly = det.get("poly")

        if not text:
            print(f"[extract_text]   [{idx:03d}] ⚠️  Empty text, skipped")
            continue

        status = "✓" if conf > min_confidence else "✗"
        print(f"[extract_text]   [{idx:03d}] {status}  conf={conf:.3f}  text='{text}'")
        if conf <= min_confidence:
            continue

        lines.append(text)
        bbox = _polygon_to_bbox(poly)
        if bbox is None:
            token = {
                "idx": idx,
                "text": text,
                "conf": conf,
            }
        else:
            x0, y0, x1, y1 = bbox
            token = {
                "idx": idx,
                "text": text,
                "conf": conf,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "cx": (x0 + x1) / 2.0,
                "cy": (y0 + y1) / 2.0,
                "w": max(0.0, x1 - x0),
                "h": max(0.0, y1 - y0),
            }
        tokens.append(token)

    print(f"\n[extract_text] Kept {len(lines)} / {raw_count} lines "
          f"(threshold={min_confidence})\n")
    return {"lines": lines, "tokens": tokens}

def extract_text(image_path: str) -> List[str]:
    """
    Run PaddleOCR on *image_path* and return a list of text lines that
    pass the confidence threshold.
    """
    payload = extract_text_payload(image_path)
    return payload.get("lines", [])


# ──────────────────────────────────────────────
# PIPELINE
# ──────────────────────────────────────────────

def process_bill(image_path: str) -> Dict[str, Any]:
    """
    Full bill-processing pipeline.

    Returns a dict with at minimum:
        {
            "merchant": str,
            "area": str,
            "date": str,
            "subtotal": float,
            "tax": float,
            "total_amount": float,
            "items": [ { product_name/name, quantity, unit_price,
                         total_price, tax, category }, … ],
            "pipeline": "llm" | "heuristic",   ← which path was used
        }
    On failure:
        { "items": [], "total_amount": 0, "error": str }
    """
    print(f"\n{'#'*60}")
    print(f"🚀 process_bill  START  –  '{image_path}'")
    print(f"{'#'*60}")

    # ── Step 1: OCR
    try:
        lines = extract_text(image_path)
    except Exception as exc:
        print(f"[process_bill] ❌ OCR step crashed: {exc}")
        return {"items": [], "total_amount": 0, "error": f"OCR error: {exc}"}

    if not lines:
        print("[process_bill] ❌ No text extracted from image")
        return {"items": [], "total_amount": 0, "error": "No text detected"}

    print(f"[process_bill] OCR produced {len(lines)} lines")

    # ── Step 2a: LLM path (primary)
    if get_settings().use_llm_process_bill:
        print("\n[process_bill] ── Trying LLM path …")
        try:
            from services.llm_service import structure_bill   # local import to keep optional

            # llm_service expects a single string with newline-separated lines
            ocr_text = "\n".join(lines)
            print(f"[process_bill] Sending {len(ocr_text)} chars to LLM")

            result = structure_bill(ocr_text)

            # Check if LLM actually returned useful data
            if result.get("llm_error"):
                print(f"[process_bill] ⚠️  LLM returned error: {result['llm_error']}")
                print("[process_bill] Falling back to heuristic parser …")
            elif not result.get("items"):
                print("[process_bill] ⚠️  LLM returned 0 items – falling back to heuristic")
            else:
                result["pipeline"] = "llm"
                print(f"\n[process_bill] ✅ LLM path succeeded  "
                      f"({len(result['items'])} items, total={result.get('total_amount')})")
                _debug_print_result(result)
                return result

        except ImportError as exc:
            print(f"[process_bill] ⚠️  llm_service not importable ({exc}) – skipping LLM")
        except Exception as exc:
            print(f"[process_bill] ❌ LLM path crashed: {exc}")
            import traceback; traceback.print_exc()

    # ── Step 2b: Heuristic fallback
    print("\n[process_bill] ── Using heuristic parser …")
    try:
        from services.receipt_parser import parse_receipt

        heuristic_result = parse_receipt(lines)
        heuristic_result["pipeline"] = "heuristic"

        # Normalise item keys to match LLM output (product_name → name)
        for item in heuristic_result.get("items", []):
            if "product_name" in item and "name" not in item:
                item["name"] = item.pop("product_name")

        print(f"\n[process_bill] ✅ Heuristic path done  "
              f"({len(heuristic_result['items'])} items, "
              f"total={heuristic_result.get('total_amount')})")
        _debug_print_result(heuristic_result)
        return heuristic_result

    except Exception as exc:
        print(f"[process_bill] ❌ Heuristic parser crashed: {exc}")
        import traceback; traceback.print_exc()
        return {"items": [], "total_amount": 0, "error": f"Parser error: {exc}"}


# ──────────────────────────────────────────────
# DEBUG HELPER
# ──────────────────────────────────────────────

def _debug_print_result(result: Dict[str, Any]) -> None:
    if not get_settings().ocr_debug:
        return
    print("\n[debug] ─── FINAL RESULT ───────────────────────────")
    print(f"  merchant    : {result.get('merchant', '')}")
    print(f"  date        : {result.get('date', '')}")
    print(f"  subtotal    : {result.get('subtotal', 0)}")
    print(f"  tax         : {result.get('tax', 0)}")
    print(f"  total_amount: {result.get('total_amount', 0)}")
    print(f"  pipeline    : {result.get('pipeline', 'unknown')}")
    print(f"  items ({len(result.get('items', []))}):")
    for i, it in enumerate(result.get("items", []), 1):
        name  = it.get("name") or it.get("product_name", "?")
        qty   = it.get("quantity", 1)
        up    = it.get("unit_price", 0)
        total = it.get("total_price", 0)
        cat   = it.get("category", "")
        print(f"    [{i:02d}] {name!r:<35} qty={qty}  unit={up:.2f}  total={total:.2f}  cat={cat}")
    print("[debug] ───────────────────────────────────────────\n")
