"""
Semantic receipt parsing via a local LLM (Ollama).

Configure via ``BillScannerServer/.env`` / environment (see ``config.Settings``):
``RECEIPT_LLM_MODE``, ``OLLAMA_URL``, ``OLLAMA_MODEL``, ``OLLAMA_TIMEOUT_SEC``,
``OLLAMA_MAX_RETRIES``.

Requires Ollama (or compatible API) with the chosen model available.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from config import get_settings
from services.categorization import categorize_item

log = logging.getLogger("llm_receipt_parser")


def llm_mode() -> str:
    return get_settings().receipt_llm_mode


def is_llm_enabled() -> bool:
    return llm_mode() in {"fallback", "always"}


def _ollama_url() -> str:
    return get_settings().ollama_url.strip()


def _ollama_model() -> str:
    return get_settings().ollama_model.strip()


def _timeout_sec() -> float:
    return float(get_settings().ollama_timeout_sec)


def _max_retries() -> int:
    return max(0, int(get_settings().ollama_max_retries))


def format_ocr_lines_for_prompt(lines: List[str], max_chars: int = 14000) -> str:
    """
    Numbered OCR lines for LLM context. Prefer this over lossy "compact" filters
    so vertical / multi-line supermarket layouts are not dropped.
    """
    cleaned = [str(l).strip() for l in lines if str(l).strip()]
    parts = [f"{i + 1:03d}|{ln}" for i, ln in enumerate(cleaned)]
    body = "\n".join(parts)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...[truncated]"
    return body


def _format_ocr_block(lines: List[str], max_chars: int = 14000) -> str:
    return format_ocr_lines_for_prompt(lines, max_chars=max_chars)


def receipt_extraction_prompt(ocr_block: str) -> str:
    """Shared instruction block + schema for Ollama (used by API LLM path)."""
    return f"""You are a receipt extractor. Given OCR lines (numbered), output ONE JSON object only.
No markdown fences, no commentary, no trailing text.

Rules:
- Include only real purchased line items. Skip: shop headers/footers; column titles (HSN, Qty, Rate…);
  tax/GST summary-only blocks; "Payment/UPI/NEFT" lines; slogans; loyalty text; URLs; GSTIN-only lines.
- Merge split OCR: if a product name continues on the next line, combine into one item name.
- Parse money as JSON numbers: strip ₹ Rs , symbols and spaces. Indian grouping (e.g. 1,234.56) → 1234.56.
- quantity: decimals for weighed goods (e.g. 0.909). If pack count is unclear, use 1.
- If unit_price missing but total_price and quantity exist: unit_price = total_price / quantity (when quantity > 0).
- If total_price missing but unit_price and quantity exist: total_price = unit_price * quantity.
- total_amount must be the FINAL amount to pay (prefer labels like Grand Total, Net Payable, Amount Due,
  Bill Amount, Total, Amount Received from customer). Do NOT use sum of MRPs, pre-discount subtotals,
  or a single line item's amount unless it is clearly the bill total.
- subtotal: pre-tax merchandise total if shown, else 0. tax: total GST/tax if shown, else 0.
- bill_date as YYYY-MM-DD if inferable, else "". bill_time as HH:MM or HH:MM:SS if visible, else "".
- category: use one of Groceries, Household, Medical, Electronics, Dining, Beverages, Snacks, Other,
  or "" if unknown (empty string is OK).

JSON schema (all keys present; use 0 or "" when unknown):
{{
  "merchant": "",
  "bill_number": "",
  "bill_date": "",
  "bill_time": "",
  "subtotal": 0,
  "tax": 0,
  "total_amount": 0,
  "items": [
    {{
      "name": "",
      "sku": "",
      "hsn_code": "",
      "quantity": 1,
      "unit_price": 0,
      "total_price": 0,
      "tax": 0,
      "category": ""
    }}
  ]
}}

OCR lines:
{ocr_block}
"""


def _build_prompt(ocr_block: str) -> str:
    return receipt_extraction_prompt(ocr_block)


def _first_balanced_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    start = text.find("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text[start:])
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    candidate = _first_balanced_json_object(text)
    if not candidate:
        return None
    try:
        obj = json.loads(candidate)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_llm_payload(
    data: Dict[str, Any],
    raw_line_count: int,
) -> Dict[str, Any]:
    normalized_items: List[Dict[str, Any]] = []

    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        if not name:
            continue
        try:
            quantity = float(item.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            quantity = 1.0
        try:
            unit_price = float(item.get("unit_price", 0) or 0)
        except (TypeError, ValueError):
            unit_price = 0.0
        try:
            total_price = float(item.get("total_price", 0) or 0)
        except (TypeError, ValueError):
            total_price = 0.0
        try:
            item_tax = float(item.get("tax", 0) or 0)
        except (TypeError, ValueError):
            item_tax = 0.0

        if total_price <= 0 and unit_price > 0 and quantity > 0:
            total_price = round(unit_price * quantity, 2)
        if unit_price <= 0 and total_price > 0 and quantity > 0:
            unit_price = round(total_price / quantity, 4)

        llm_cat = str(item.get("category", "") or "").strip()
        category = llm_cat if llm_cat and llm_cat.lower() != "other" else categorize_item(name)

        hsn_raw = str(item.get("hsn_code", "") or item.get("hsn", "") or "").strip()
        hsn_code = hsn_raw or None

        normalized_items.append(
            {
                "name": name,
                "product_name": name,
                "sku": str(item.get("sku", "") or "").strip() or None,
                "hsn_code": hsn_code,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "tax": item_tax,
                "category": category,
            }
        )

    try:
        subtotal = float(data.get("subtotal", 0) or 0)
    except (TypeError, ValueError):
        subtotal = 0.0
    try:
        tax = float(data.get("tax", 0) or 0)
    except (TypeError, ValueError):
        tax = 0.0
    try:
        total_amount = float(data.get("total_amount", 0) or 0)
    except (TypeError, ValueError):
        total_amount = 0.0

    if total_amount <= 0 and normalized_items:
        total_amount = float(
            sum(float(i.get("total_price") or 0) for i in normalized_items)
        )
    if subtotal <= 0 and normalized_items and total_amount > 0:
        subtotal = total_amount - tax if total_amount > tax else total_amount

    merchant = str(data.get("merchant", "") or "").strip()
    bill_number = str(data.get("bill_number", "") or "").strip() or None
    bill_date = (
        str(data.get("bill_date", "") or data.get("date", "") or "").strip() or None
    )
    bill_time = str(data.get("bill_time", "") or "").strip() or None

    return {
        "merchant": merchant,
        "bill_number": bill_number,
        "bill_date": bill_date,
        "bill_time": bill_time,
        "subtotal": subtotal,
        "tax": tax,
        "total_tax": tax,
        "total_amount": total_amount,
        "items": normalized_items,
        "raw_line_count": raw_line_count,
        "parse_source": "llm",
    }


def parse_receipt_llm(lines: List[str]) -> Optional[Dict[str, Any]]:
    """
    Call Ollama and return a dict compatible with parse_receipt(), or None on failure.
    """
    if not lines:
        return None

    ocr_block = _format_ocr_block(lines)
    prompt = _build_prompt(ocr_block)
    url = _ollama_url()
    model = _ollama_model()
    timeout = _timeout_sec()
    retries = _max_retries()

    last_err: Optional[str] = None
    raw_output = ""

    for attempt in range(retries + 1):
        try:
            r = requests.post(
                url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "10m",
                    "options": {"temperature": 0.1},
                },
                timeout=timeout,
            )
            r.raise_for_status()
            raw_output = str(r.json().get("response", "") or "")
            break
        except Exception as exc:
            last_err = str(exc)
            log.warning("Ollama request failed (%s/%s): %s", attempt + 1, retries + 1, exc)
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
            else:
                log.error("Ollama gave up after retries; last error: %s", last_err)
                return None

    data = _extract_json_object(raw_output)
    if not data:
        log.error("LLM output was not valid JSON (preview): %s", raw_output[:500])
        return None

    out = _normalize_llm_payload(data, raw_line_count=len(lines))
    out["llm_model"] = model
    if last_err:
        out["llm_last_connect_error"] = last_err
    log.info(
        "LLM parse OK: items=%s total=%s",
        len(out.get("items") or []),
        out.get("total_amount"),
    )
    return out


def llm_result_usable(result: Optional[Dict[str, Any]]) -> bool:
    if not result:
        return False
    items = result.get("items") or []
    total = float(result.get("total_amount") or 0)
    return len(items) > 0 or total > 0


def heuristic_looks_weak(heuristic: Dict[str, Any], lines: List[str]) -> bool:
    """Signals that OCR is rich but structured parsing likely failed."""
    if len(lines) < 4:
        return False
    items = heuristic.get("items") or []
    total = float(heuristic.get("total_amount") or 0)
    if len(items) == 0:
        return True
    if total <= 0 and len(lines) >= 10:
        return True
    subtotal_items = sum(float(i.get("total_price") or 0) for i in items)
    if total > 0 and subtotal_items > 0:
        ratio = max(total, subtotal_items) / max(min(total, subtotal_items), 1e-6)
        if ratio > 4.0:
            return True
    return False


def llm_preferred_over_heuristic(
    llm_res: Dict[str, Any],
    heuristic: Dict[str, Any],
) -> bool:
    li = llm_res.get("items") or []
    hi = heuristic.get("items") or []
    if len(li) > len(hi):
        return True
    if len(hi) == 0 and len(li) > 0:
        return True
    lt = float(llm_res.get("total_amount") or 0)
    ht = float(heuristic.get("total_amount") or 0)
    if len(hi) > 0 and len(li) > 0 and ht <= 0 and lt > 0:
        return True
    return False
