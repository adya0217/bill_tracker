"""
llm_service.py  –  Ollama LLM receipt structuring

Sends compacted OCR text to a local Ollama model and parses the JSON response
into a normalised bill dict.

DEBUG logging covers:
  • compact step (how many lines were kept / dropped)
  • prompt preview
  • raw LLM output
  • JSON parsing
  • each item normalisation
  • final totals reconciliation
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

import requests

from config import get_settings
from services.categorization import categorize_item
from services.llm_receipt_parser import format_ocr_lines_for_prompt, receipt_extraction_prompt


# ──────────────────────────────────────────────
# PROMPT  (same rules/schema as API LLM path — see receipt_extraction_prompt)
# ──────────────────────────────────────────────

def _build_prompt(ocr_text: str) -> str:
    lines = [ln.strip() for ln in (ocr_text or "").splitlines() if ln.strip()]
    print(f"\n[compact] numbered OCR lines: {len(lines)} (full text up to char cap)")
    block = format_ocr_lines_for_prompt(lines)
    print(f"\n[prompt] OCR block ({len(block)} chars):\n{block[:600]}"
          f"{'…' if len(block) > 600 else ''}\n")
    return receipt_extraction_prompt(block)


# ──────────────────────────────────────────────
# OLLAMA CALL
# ──────────────────────────────────────────────

def _call_ollama(prompt: str) -> Optional[str]:
    """
    Call Ollama with retries. Returns raw string output or None on failure.
    """
    cfg = get_settings()
    ollama_url = cfg.ollama_url.strip()
    model_name = cfg.ollama_model.strip()
    request_timeout = float(cfg.ollama_timeout_sec)
    max_retries = max(0, int(cfg.ollama_max_retries))

    print(f"\n[ollama] Sending request to {ollama_url}  model={model_name}")
    print(f"[ollama] prompt length: {len(prompt)} chars")

    last_error = ""
    for attempt in range(max_retries + 1):
        print(f"[ollama] Attempt {attempt + 1}/{max_retries + 1} …")
        try:
            t0 = time.time()
            response = requests.post(
                ollama_url,
                json={
                    "model":      model_name,
                    "prompt":     prompt,
                    "stream":     False,
                    "keep_alive": "30m",
                    "options":    {"temperature": 0},
                },
                timeout=request_timeout,
            )
            elapsed = time.time() - t0
            response.raise_for_status()
            raw = response.json().get("response", "")
            print(f"[ollama] ✓ Got response in {elapsed:.1f}s  ({len(raw)} chars)")
            return raw

        except requests.exceptions.Timeout:
            last_error = "Timeout"
            print(f"[ollama] ❌ Timeout after {request_timeout}s")
        except requests.exceptions.ConnectionError as exc:
            last_error = str(exc)
            print(f"[ollama] ❌ Connection error (is Ollama running?): {exc}")
        except Exception as exc:
            last_error = str(exc)
            print(f"[ollama] ❌ Error: {exc}")

        if attempt < max_retries:
            sleep = 1.5 * (attempt + 1)
            print(f"[ollama] Retrying in {sleep:.1f}s …")
            time.sleep(sleep)

    print(f"[ollama] ❌ All {max_retries + 1} attempts failed. Last error: {last_error}")
    return None


# ──────────────────────────────────────────────
# JSON EXTRACTION
# ──────────────────────────────────────────────

def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to extract a JSON object from raw LLM output.
    Tries multiple strategies so minor formatting quirks don't break things.
    """
    print("\n[json] Attempting to extract JSON from LLM output …")

    # Strategy 1: strip markdown fences, parse directly
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    print(f"[json] cleaned (first 400 chars):\n{cleaned[:400]}")

    strategies = [
        ("direct parse",          lambda s: json.loads(s)),
        ("first {...} match",     lambda s: json.loads(re.search(r"\{.*\}", s, re.DOTALL).group())),
        ("relaxed brace scan",    _brace_scan),
    ]

    for name, fn in strategies:
        try:
            data = fn(cleaned)
            print(f"[json] ✓ Parsed via '{name}'")
            return data
        except Exception as exc:
            print(f"[json]   '{name}' failed: {exc}")

    print("[json] ❌ All JSON extraction strategies failed")
    return None


def _brace_scan(text: str) -> Dict[str, Any]:
    """Find the longest balanced { … } substring and parse it."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No '{' found")
    depth  = 0
    end    = start
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0:
            end = i
            break
    candidate = text[start : end + 1]
    return json.loads(candidate)


# ──────────────────────────────────────────────
# ITEM NORMALISATION
# ──────────────────────────────────────────────

def _normalise_items(raw_items: List[Any]) -> List[Dict[str, Any]]:
    normalised: List[Dict[str, Any]] = []

    print(f"\n[items] Normalising {len(raw_items)} raw items …")

    for idx, item in enumerate(raw_items):
        print(f"\n[items]  [{idx:02d}] raw: {item}")
        try:
            name = str(item.get("name", "") or "").strip()

            qty        = float(item.get("quantity",   1)  or 1)
            unit_price = float(item.get("unit_price", 0)  or 0)
            total_raw  = item.get("total_price")
            total_price = float(total_raw if total_raw is not None else qty * unit_price)
            item_tax   = float(item.get("tax",        0)  or 0)

            print(f"[items]       name='{name}'  qty={qty}  unit={unit_price}  total={total_price}")

            # ── infer missing values
            if total_price <= 0 and unit_price > 0:
                total_price = round(qty * unit_price, 2)
                print(f"[items]       inferred total_price={total_price}")
            if unit_price <= 0 and total_price > 0 and qty > 0:
                unit_price = round(total_price / qty, 2)
                print(f"[items]       inferred unit_price={unit_price}")

            if not name:
                print("[items]       ⚠️  Skipping item with empty name")
                continue

            # ── category: prefer LLM, fall back to ML/keywords
            llm_cat  = str(item.get("category", "") or "").strip()
            category = llm_cat if llm_cat and llm_cat.lower() != "other" else categorize_item(name)
            print(f"[items]       category: llm='{llm_cat}' → final='{category}'")

            hsn_raw = str(item.get("hsn_code", "") or item.get("hsn", "") or "").strip()

            normalised.append({
                "name":         name,
                "product_name": name,
                "sku":          str(item.get("sku", "") or "").strip(),
                "hsn_code":     hsn_raw or None,
                "quantity":     qty,
                "unit_price":   unit_price,
                "total_price":  total_price,
                "tax":          item_tax,
                "category":     category,
            })
            print(f"[items]       ✓ accepted")

        except Exception as exc:
            print(f"[items]       ❌ Skipped due to error: {exc}  raw={item}")

    print(f"\n[items] {len(normalised)}/{len(raw_items)} items normalised successfully")
    return normalised


# ──────────────────────────────────────────────
# TOTALS RECONCILIATION
# ──────────────────────────────────────────────

def _reconcile_totals(
    data: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> tuple[float, float, float]:
    """
    Return (subtotal, tax, total_amount) filling in missing values from items.
    """
    subtotal     = float(data.get("subtotal",     0) or 0)
    total_amount = float(data.get("total_amount", 0) or 0)
    tax          = float(data.get("tax",          0) or 0)

    item_sum = round(sum(it.get("total_price", 0) or 0 for it in items), 2)

    print(f"\n[totals] LLM says  subtotal={subtotal}  tax={tax}  total={total_amount}")
    print(f"[totals] Item sum = {item_sum}")

    if total_amount <= 0:
        total_amount = item_sum
        print(f"[totals] total_amount was 0 → using item sum: {total_amount}")

    if subtotal <= 0:
        if tax > 0 and total_amount > tax:
            subtotal = round(total_amount - tax, 2)
            print(f"[totals] subtotal inferred as total - tax: {subtotal}")
        else:
            subtotal = total_amount
            print(f"[totals] subtotal was 0 → using total: {subtotal}")

    if tax <= 0 and total_amount > subtotal + 0.005:
        tax = round(total_amount - subtotal, 2)
        print(f"[totals] tax inferred from total-subtotal: {tax}")

    print(f"[totals] Final → subtotal={subtotal}  tax={tax}  total={total_amount}")
    return subtotal, tax, total_amount


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────

def structure_bill(ocr_text: str) -> Dict[str, Any]:
    """
    Convert raw OCR text into a structured bill dict via Ollama.

    On success returns:
        {
            merchant, area, date, subtotal, tax, total_amount,
            items: [ {name, sku, quantity, unit_price, total_price, tax, category} ]
        }

    On failure (all retries exhausted) returns the same schema with empty/zero
    values plus "llm_error" key containing the error message.
    """
    print("\n" + "="*60)
    print("🤖  LLM SERVICE  –  structure_bill  START")
    print(f"    OCR text length: {len(ocr_text)} chars")
    print("="*60)

    _EMPTY = {
        "merchant": "",
        "area": "",
        "bill_date": None,
        "bill_time": None,
        "bill_number": None,
        "date": "",
        "subtotal": 0,
        "tax": 0,
        "total_tax": 0,
        "total_amount": 0,
        "items": [],
    }

    # ── 1. build prompt
    prompt = _build_prompt(ocr_text)

    # ── 2. call Ollama
    raw_output = _call_ollama(prompt)
    if raw_output is None:
        return {**_EMPTY, "llm_error": "Ollama call failed (check logs)"}

    print(f"\n[llm] Raw output preview:\n{raw_output[:500]}"
          f"{'…' if len(raw_output) > 500 else ''}")

    # ── 3. extract JSON
    data = _extract_json(raw_output)
    if data is None:
        return {**_EMPTY, "llm_error": "JSON extraction failed"}

    # ── 4. normalise items
    items = _normalise_items(data.get("items", []))

    # ── 5. reconcile totals
    subtotal, tax, total_amount = _reconcile_totals(data, items)

    bill_date_str = str(data.get("bill_date", "") or data.get("date", "") or "").strip()
    bill_time_str = str(data.get("bill_time", "") or "").strip()
    bill_number_str = str(data.get("bill_number", "") or "").strip()

    structured: Dict[str, Any] = {
        "merchant":      str(data.get("merchant", "") or "").strip(),
        "area":          str(data.get("area", "") or "").strip(),
        "bill_date":     bill_date_str or None,
        "bill_time":     bill_time_str or None,
        "bill_number":   bill_number_str or None,
        "date":          bill_date_str,
        "subtotal":      subtotal,
        "tax":           tax,
        "total_tax":     tax,
        "total_amount":  total_amount,
        "items":         items,
    }

    print("\n" + "="*60)
    print(f"✅  LLM SERVICE  –  DONE  ({len(items)} items, total={total_amount})")
    print("="*60 + "\n")

    return structured
