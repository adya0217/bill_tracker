import requests
import json
import re
import time
from typing import Dict, Any, List

from services.categorization import categorize_item

# -----------------------------
# CONFIG
# -----------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "ministral-3:3b"
REQUEST_TIMEOUT = 600
MAX_RETRIES = 2


def _compact_receipt_text(ocr_text: str, max_lines: int = 180) -> str:
 
    lines = [ln.strip() for ln in (ocr_text or "").splitlines() if ln.strip()]
    if not lines:
        return ""

    header = lines[:25]
    footer = lines[-25:] if len(lines) > 25 else []

    item_like: List[str] = []
    totals_like: List[str] = []

    for ln in lines:
        low = ln.lower()
        has_letters = bool(re.search(r"[a-zA-Z]", ln))
        nums = re.findall(r"\d+(?:[.,]\d+)?", ln)

        if any(k in low for k in ["total", "net", "subtotal", "tax", "gst", "sgst", "cgst", "amount"]):
            totals_like.append(ln)
            continue

        # Item lines often have a name and 2-3 numeric columns (qty/rate/amount)
        if has_letters and len(nums) >= 2:
            item_like.append(ln)

    # Deduplicate while preserving order
    def dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out = []
        for s in seq:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    combined = dedupe(header + item_like + totals_like + footer)
    combined = combined[:max_lines]
    return "\n".join(combined)


# -----------------------------
# PROMPT BUILDER
# -----------------------------
def _build_prompt(ocr_text: str) -> str:
    compact = _compact_receipt_text(ocr_text)
    return f"""
Extract structured data from this receipt OCR.

Return ONLY valid JSON. No markdown. No explanation.

Rules:
- Numbers must be numbers (not strings)
- Date should be YYYY-MM-DD if possible (else empty string)
- If quantity missing assume 1
- If unit_price missing but total_price present, infer unit_price = total_price / quantity
- If total_price missing but unit_price present, infer total_price = unit_price * quantity
- If subtotal/tax missing use 0

Output JSON schema:
{{
  "merchant": "",
  "area": "",
  "date": "",
  "subtotal": 0,
  "tax": 0,
  "total_amount": 0,
  "items": [
    {{
      "name": "",
      "sku": "",
      "quantity": 1,
      "unit_price": 0,
      "total_price": 0,
      "tax": 0,
      "category": ""
    }}
  ]
}}

OCR lines:
{compact}
"""


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def structure_bill(ocr_text: str) -> Dict[str, Any]:
    print("🤖 Sending text to Ollama...")
    prompt = _build_prompt(ocr_text)

    raw_output = ""
    last_error: str = ""

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    # keep model loaded longer; helps with repeated scans
                    "keep_alive": "30m",
                    "options": {"temperature": 0},
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            raw_output = response.json().get("response", "")
            break
        except Exception as e:
            last_error = str(e)
            print(f"❌ Ollama request failed (attempt {attempt + 1}/{MAX_RETRIES + 1}):", e)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * (attempt + 1))
            else:
                return {
                    "merchant": "",
                    "area": "",
                    "date": "",
                    "subtotal": 0,
                    "tax": 0,
                    "total_amount": 0,
                    "items": [],
                    "llm_error": last_error,
                }

    print("🧠 Raw LLM Output Preview:")
    print(raw_output[:400])

    # -----------------------------
    # CLEAN MARKDOWN / NOISE
    # -----------------------------
    cleaned = re.sub(r"```json|```", "", raw_output).strip()

    # -----------------------------
    # EXTRACT JSON SAFELY
    # -----------------------------
    try:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")

        data = json.loads(match.group())

    except Exception as e:
        print("❌ JSON parsing failed:", e)
        print("⚠️ Cleaned output:", cleaned)
        return {"merchant": "", "items": [], "total_amount": 0}

    # -----------------------------
    # POST-PROCESS ITEMS
    # -----------------------------
    normalized_items: List[Dict[str, Any]] = []

    for item in data.get("items", []):
        try:
            name = str(item.get("name", "")).strip()

            quantity = float(item.get("quantity", 1) or 1)
            unit_price = float(item.get("unit_price", 0) or 0)
            total_price = float(
                item.get("total_price", quantity * unit_price) or quantity * unit_price
            )
            item_tax = float(item.get("tax", 0) or 0)

            # Infer missing numbers when possible
            if total_price <= 0 and unit_price > 0 and quantity > 0:
                total_price = float(quantity * unit_price)
            if unit_price <= 0 and total_price > 0 and quantity > 0:
                unit_price = float(total_price / quantity)

            # Prefer LLM category, but fall back to ML/keywords
            llm_category = str(item.get("category", "") or "").strip()
            category = llm_category or categorize_item(name)

            normalized_items.append(
                {
                    "name": name,
                    "sku": str(item.get("sku", "") or "").strip(),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "tax": item_tax,
                    "category": category,
                }
            )

        except Exception as e:
            print("⚠️ Skipping invalid item:", item, e)

    subtotal = float(data.get("subtotal", 0) or 0)
    total_amount = float(data.get("total_amount", subtotal) or subtotal)
    tax = float(data.get("tax", max(total_amount - subtotal, 0)) or 0)
    merchant = str(data.get("merchant", "") or "").strip()
    area = str(data.get("area", "") or "").strip()
    bill_date = str(data.get("date", "") or "").strip()

    # If totals are missing/zero, fall back to sum of line totals
    if total_amount <= 0 and normalized_items:
        total_amount = float(sum(it.get("total_price", 0) or 0 for it in normalized_items))
        if subtotal <= 0:
            subtotal = total_amount

    structured: Dict[str, Any] = {
        "merchant": merchant,
        "area": area,
        "date": bill_date,
        "subtotal": subtotal,
        "tax": tax,
        "total_amount": total_amount,
        "items": normalized_items,
    }

    print("✅ Structured & normalized bill:")
    print(structured)

    return structured