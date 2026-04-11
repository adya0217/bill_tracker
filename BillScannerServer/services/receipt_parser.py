
"""

Used when LLM is unavailable or as a cross-check.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

import services.llm_receipt_parser as _llm_rp

NumberToken = Tuple[str, int, int]

# Captures numbers such as:
#  - 12
#  - 12.50
#  - 1,250
#  - 1,250.75
_NUMBER_TOKEN_RE = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?(?!\d)"
)

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _to_float(tok: str) -> Optional[float]:
    """Convert a raw token string to float, handling comma formats."""
    try:
        tok = (tok or "").strip()
        tok = re.sub(r"[^\d,.\-]", "", tok)
        if not tok:
            return None

        if "," in tok and "." in tok:
            # "1,250.75" -> "1250.75"
            tok = tok.replace(",", "")
        elif "," in tok:
            # Could be either thousands separators ("1,250")
            # or decimal comma ("12,50").
            parts = tok.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                tok = ".".join(parts)
            else:
                tok = "".join(parts)

        # e.g. "1.000" -> quantity 1, not price 1.000
        if re.match(r"^\d+\.000$", tok):
            val = float(tok.split(".")[0])
            print(f"      [_to_float] '{tok}' -> integer-like -> {val}")
            return val


        val = float(tok)
        print(f"      [_to_float] '{tok}' -> {val}")
        return val
    except Exception as exc:
        print(f"      [_to_float] '{tok}' -> FAILED ({exc})")
        return None


def _extract_number_tokens(line: str) -> List[NumberToken]:
    """Return all numeric tokens with their span in the line."""
    matches = list(_NUMBER_TOKEN_RE.finditer(line))
    tokens = [(m.group(0), m.start(), m.end()) for m in matches]
    print(f"      [numbers] {[t[0] for t in tokens]}")
    return tokens


# ──────────────────────────────────────────────
# LINE FILTER
# ──────────────────────────────────────────────

# Words that almost never appear in item lines (header/footer/meta)
_SKIP_WORDS = {
    "invoice", "gst", "cin", "phone", "mob", "fssai",
    "gstin", "address", "thank", "visit", "website",
    "operator", "cashier", "terminal", "pos",
}

# Words that *can* appear in item names but also in totals rows.
# We allow them unless the line has NO other alphabetic content.
_SOFT_SKIP_WORDS = {"total", "amount", "tax", "rate", "subtotal", "net", "cash"}
_MERCHANT_SKIP_WORDS = {
    "gst", "gstin", "cin", "fssai", "phone", "mob", "bill", "invoice",
    "cashier", "vou", "hsn", "sac", "code", "particular", "qty", "rate", "value",
    "duplicate", "copy", "pickup", "narne",
}
_MERCHANT_NOISE_PREFIXES = ("dupl", "copy", "triplicate")
_NON_ITEM_NAME_HINTS = {
    "payment details", "tax summary", "amount received", "received amount", "balance paid",
    "gross sale", "net payable", "discount", "disc:", "items:", "qty:", "service amount",
    "paid amount", "print date", "printed on", "printed by", "signature", "whatsapp",
    "invoice no", "bill no", "cashier", "date:", "time", "token no",
    "upi", "txn", "txnid", "ref.no", "points", "visit again", "for queries", "email",
}


def _is_numeric_only_line(line: str) -> bool:
    
    raw = line.strip()
    if not raw:
        return False
    # Allow common OCR separators while requiring at least one digit.
    if not re.fullmatch(r"[\d\s,.:/-]+", raw):
        return False
    return bool(re.search(r"\d", raw))


def _is_totals_line(line: str) -> bool:
    low = line.lower()
    return any(k in low for k in ("total", "subtotal", "discount", "net total", "grand total"))


def _looks_like_hsn_code(token: str) -> bool:
    token = (token or "").strip()
    return bool(re.fullmatch(r"\d{4,8}", token))


def _looks_like_qty_token(token: str) -> bool:
    tok = (token or "").strip().lower()
    if tok in {"i", "l", "is"}:
        return True
    val = _to_float(tok)
    return val is not None and 0 < val <= 50


def _qty_from_token(token: str) -> float:
    tok = (token or "").strip().lower()
    if tok in {"i", "l", "is"}:
        return 1.0
    val = _to_float(tok)
    if val is None or val <= 0:
        return 1.0
    return float(val)


def _build_rows_from_tokens(tokens: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group OCR tokens into visual rows using y-center proximity.
    """
    usable: List[Dict[str, Any]] = []
    for t in tokens:
        if not isinstance(t, dict):
            continue
        if "cy" not in t or "cx" not in t:
            continue
        text = str(t.get("text", "") or "").strip()
        if not text:
            continue
        conf = float(t.get("conf", 1.0) or 0.0)
        if conf < 0.30:
            continue
        item = dict(t)
        item["text"] = text
        item["cx"] = float(item["cx"])
        item["cy"] = float(item["cy"])
        item["h"] = float(item.get("h", 18.0) or 18.0)
        usable.append(item)

    if not usable:
        return []

    usable.sort(key=lambda x: (x["cy"], x["cx"]))
    heights = sorted(max(8.0, t["h"]) for t in usable)
    median_h = heights[len(heights) // 2]
    row_tol = max(10.0, median_h * 0.65)

    rows: List[List[Dict[str, Any]]] = []
    row_centers: List[float] = []

    for tok in usable:
        if not rows:
            rows.append([tok])
            row_centers.append(tok["cy"])
            continue
        if abs(tok["cy"] - row_centers[-1]) <= row_tol:
            rows[-1].append(tok)
            row_centers[-1] = (row_centers[-1] * (len(rows[-1]) - 1) + tok["cy"]) / len(rows[-1])
        else:
            rows.append([tok])
            row_centers.append(tok["cy"])

    for row in rows:
        row.sort(key=lambda x: x["cx"])
    return rows


def _row_text(row: List[Dict[str, Any]]) -> str:
    return " ".join(t.get("text", "").strip() for t in row if t.get("text"))


def _looks_like_table_header_blob(low: str) -> bool:
    has_desc = any(
        k in low
        for k in (
            "description",
            "scription",
            "particular",
            "item",
            "service name",
            "service",
            "product name",
            "sl.",
            "sl ",
        )
    )
    has_qty = any(
        k in low
        for k in ("qty", "oty", "qly", "qly.", "qty:", "qty.", "items/qty")
    )
    has_rate = any(k in low for k in ("rate", "price", "rale", "mrp"))
    has_amt = any(
        k in low
        for k in ("amount", "value", "disc.amount", "disc amount", "amt")
    )
    full = has_desc and has_qty and has_rate and has_amt
    # e.g. "Item" + "Qty.Price Amount" (OCR glues column titles)
    simple_grid = ("item" in low) and has_qty and has_rate and has_amt
    return full or simple_grid


def _try_split_glued_table_numbers(s: str) -> Optional[List[str]]:
    """
    Undo common thermal-printer OCR glue: quantity + unit price + line total
    merged into one token (e.g. 1 + 140.00 + 140.00 -> '1140.00140.00').
    Returns separate strings to feed vertical/hsn parsers.
    """
    s = (s or "").strip()
    if not s or not re.match(r"^[\d.]+$", s):
        return None
    if s.count(".") < 2:
        return None

    def _pair_ok(u: str, t: str) -> bool:
        try:
            fu = float(u)
            ft = float(t)
        except ValueError:
            return False
        if not (0 < fu <= 100_000 and 0 < ft <= 1_000_000):
            return False
        return True

    # Pattern: 0.1 + 440.00 + 44.00 (weighed item)
    m = re.fullmatch(r"(\d\.\d)(\d{2,5}\.\d{2})(\d{2,5}\.\d{2})", s)
    if m:
        q, u, t = m.group(1), m.group(2), m.group(3)
        if _pair_ok(u, t):
            fq = float(q)
            if 0 < fq <= 50 and abs(fq * float(u) - float(t)) <= max(1.5, float(t) * 0.03):
                return [q, u, t]

    # Integer qty + two money fields
    for q_len in (1, 2):
        if len(s) <= q_len:
            continue
        q = s[:q_len]
        if not q.isdigit():
            continue
        rest = s[q_len:]
        m2 = re.fullmatch(r"(\d{2,5}\.\d{2})(\d{2,5}\.\d{2})", rest)
        if not m2:
            continue
        u, t = m2.group(1), m2.group(2)
        if not _pair_ok(u, t):
            continue
        fq, fu, ft = float(q), float(u), float(t)
        if fq <= 0 or fq > 50:
            continue
        if abs(fq * fu - ft) <= max(2.0, ft * 0.04):
            return [str(int(fq)) if fq == int(fq) else q, u, t]

    # Two-part glue: 0.1 + 440.00 (amount on next OCR line)
    m3 = re.fullmatch(r"(\d\.\d)(\d{2,5}\.\d{2})", s)
    if m3:
        q, u = m3.group(1), m3.group(2)
        if 0 < float(u) <= 100_000:
            fq = float(q)
            if 0 < fq <= 50:
                return [q, u]

    return None


def _expand_glued_numeric_ocr_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for raw in lines:
        part = _try_split_glued_table_numbers(raw)
        if part:
            print(f"   [ocr-fix] split glued line '{raw}' -> {part}")
            out.extend(part)
        else:
            out.append(raw)
    return out


def _find_header_row_idx(rows: List[List[Dict[str, Any]]], max_scan: int = 60) -> int:
    """
    Find header row index using a small sliding window.
    This handles OCR where header words are split across adjacent rows.
    """
    upto = min(len(rows), max_scan)
    for idx in range(upto):
        merged = " ".join(_row_text(rows[j]).lower() for j in range(idx, min(idx + 3, upto)))
        if _looks_like_table_header_blob(merged):
            return idx
    return -1


def _find_header_line_idx(lines: List[str], max_scan: int = 80) -> int:
    upto = min(len(lines), max_scan)
    for idx in range(upto):
        merged = " ".join((lines[j] or "").strip().lower() for j in range(idx, min(idx + 3, upto)))
        if _looks_like_table_header_blob(merged):
            return idx
    return -1


def _extract_numeric_values(tokens: List[Dict[str, Any]]) -> List[float]:
    vals: List[float] = []
    for t in tokens:
        v = _to_float(str(t.get("text", "")))
        if v is not None and v > 0:
            vals.append(float(v))
    return vals


def _parse_coord_table_rows(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  
    rows = _build_rows_from_tokens(tokens)
    if not rows:
        print("   [coord] no coordinate rows available")
        return []

    header_idx = _find_header_row_idx(rows, max_scan=60)
    header_row: List[Dict[str, Any]] = rows[header_idx] if header_idx >= 0 else []

    if header_idx < 0:
        print("   [coord] table header not detected")
        return []

    def _anchor_x(keys: Tuple[str, ...], default: float) -> float:
        for tok in header_row:
            txt = tok.get("text", "").lower()
            if any(k in txt for k in keys):
                return float(tok["cx"])
        return default

    row_xs = [float(t["cx"]) for t in header_row] or [0.0, 100.0, 200.0, 300.0]
    left_x = min(row_xs)
    right_x = max(row_xs)
    desc_x = _anchor_x(("description", "particular", "item", "service"), left_x)
    qty_x = _anchor_x(("qty", "oty"), left_x + (right_x - left_x) * 0.33)
    rate_x = _anchor_x(("rate", "price"), left_x + (right_x - left_x) * 0.62)
    value_x = _anchor_x(("value", "amount"), left_x + (right_x - left_x) * 0.85)
    if qty_x <= desc_x:
        qty_x = (desc_x + rate_x) / 2.0
    b1 = (desc_x + qty_x) / 2.0
    b2 = (qty_x + rate_x) / 2.0
    b3 = (rate_x + value_x) / 2.0
    print(f"   [coord] header at row={header_idx}  boundaries=({b1:.1f},{b2:.1f},{b3:.1f})")

    col_span = float(b3) - float(b1)
    if col_span < 12.0 or abs(b2 - b1) < 3.0 or abs(b3 - b2) < 3.0:
        print("   [coord] degenerate column layout (OCR boxes collapsed) — skip coord mode")
        return []
    if (right_x - left_x) < 20.0 and len(header_row) <= 2:
        print("   [coord] header row too narrow for reliable columns — skip coord mode")
        return []

    items: List[Dict[str, Any]] = []
    pending_name = ""

    def _is_code_like_desc(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return True
        alpha = re.findall(r"[a-z]+", t)
        if not alpha:
            return True
        allowed = {"kg", "g", "gm", "ml", "l", "ea", "nos", "pc", "uom"}
        return all(a in allowed for a in alpha)

    for row in rows[header_idx + 1:]:
        line = _row_text(row).strip()
        low = line.lower()
        if not line:
            continue
        if any(k in low for k in ("items", "total qty", "sub total", "grand total", "net total", "amount received", "breakup", "saved rs", "card payment", "thanks", "visit again", "payment details", "tax summary", "received amount", "points", "for queries", "email")):
            print(f"   [coord] stop at footer row: '{line}'")
            break
        if any(k in low for k in ("cgst", "sgst", "igst", "gst @")):
            continue
        # Skip residual header rows in split-header OCR.
        if any(k in low for k in ("description", "scription", "qty", "qly", "rate", "rale", "amount", "disc.amount")):
            continue

        desc_tokens: List[Dict[str, Any]] = []
        qty_tokens: List[Dict[str, Any]] = []
        rate_tokens: List[Dict[str, Any]] = []
        value_tokens: List[Dict[str, Any]] = []

        for tok in row:
            cx = float(tok["cx"])
            if cx < b1:
                desc_tokens.append(tok)
            elif cx < b2:
                qty_tokens.append(tok)
            elif cx < b3:
                rate_tokens.append(tok)
            else:
                value_tokens.append(tok)

        desc_text = " ".join(t["text"] for t in desc_tokens).strip()
        desc_text = re.sub(r"\s+", " ", desc_text).strip(".-/ ")
        # Remove leading HSN code if present.
        desc_text = re.sub(r"^\d{4,8}\s+", "", desc_text).strip()
        if desc_text and any(k in desc_text.lower() for k in _NON_ITEM_NAME_HINTS):
            continue

        all_vals = _extract_numeric_values(row)
        if not all_vals:
            if desc_text and re.search(r"[A-Za-z]", desc_text) and not _is_code_like_desc(desc_text):
                pending_name = f"{pending_name} {desc_text}".strip() if pending_name else desc_text
            continue

        qty = None
        for qtok in qty_tokens:
            qv = _parse_qty_token(str(qtok.get("text", "")))
            if qv is not None:
                qty = float(qv)
                break
        if qty is None and all_vals:
            first = all_vals[0]
            if 0 < first <= 20:
                qty = first
        if qty is None:
            qty = 1.0

        rate_vals = _extract_numeric_values(rate_tokens)
        value_vals = _extract_numeric_values(value_tokens)

        if rate_vals:
            unit_price = rate_vals[0]
        elif len(all_vals) >= 2:
            # Try arithmetic-consistent unit among all row numbers.
            best_unit = all_vals[0]
            best_diff = 10**12
            for cand in all_vals:
                if cand <= 0:
                    continue
                exp = qty * cand
                diff = min(abs(exp - v) for v in all_vals)
                if diff < best_diff:
                    best_diff = diff
                    best_unit = cand
            unit_price = best_unit
        else:
            unit_price = all_vals[-1]

        expected_total = qty * unit_price
        if value_vals:
            total_price = min(value_vals, key=lambda v: abs(v - expected_total))
        elif len(all_vals) >= 2:
            total_price = min(all_vals, key=lambda v: abs(v - expected_total))
        else:
            total_price = expected_total

        if abs(total_price - expected_total) > max(10.0, expected_total * 0.35):
            total_price = round(expected_total, 2)

        if not (0 < qty <= 50 and 0 < unit_price <= 50_000 and 0 < total_price <= 500_000):
            continue

        item_name = desc_text
        if pending_name:
            if not item_name or _is_code_like_desc(item_name):
                item_name = pending_name
            elif item_name.lower() not in pending_name.lower():
                item_name = f"{pending_name} {item_name}".strip()
        pending_name = ""
        item_name = re.sub(r"\s+", " ", item_name).strip()
        if not item_name or _is_code_like_desc(item_name):
            continue

        item = {
            "product_name": item_name,
            "quantity": float(qty),
            "unit_price": float(unit_price),
            "total_price": float(total_price),
            "tax": 0.0,
        }
        print(f"   [coord] accepted row -> {item}")
        items.append(item)

    print(f"   [coord] parsed items: {len(items)}")
    return items


def _parse_hsn_item_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parse supermarket-like layouts:
      HSN | Particulars | Qty/Kg | Rate | Value
    where OCR emits one token per line.
    """
    items: List[Dict[str, Any]] = []

    header_idx = _find_header_line_idx(lines, max_scan=80)
    if header_idx < 0:
        print("   [hsn] header not found, skip hsn mode")
        return items

    # Start after local header block only; avoids jumping to TAX SUMMARY "NET VALUE".
    start = min(len(lines), header_idx + 3)
    print(f"   [hsn] header detected, scanning rows from index {start}")

    i = start
    while i < len(lines):
        token = lines[i].strip()
        low = token.lower()
        if not token:
            i += 1
            continue
        if any(k in low for k in ("items:", "breakup", "amount received", "received amount", "card payment", "saved rs", "includes", "payment details", "tax summary", "points", "for queries", "email", "net payable", "gross sale")):
            print(f"   [hsn] stop at summary/footer line: '{token}'")
            break
        if any(k in low for k in ("cgst", "sgst", "igst")) or token in {"@", "<", "-", "*"}:
            i += 1
            continue

        # Either:
        #   1) "040510" + next line name
        #   2) "250100 TATA SALT-1kg" in one line
        one_line_match = re.match(r"^(\d{4,8})\s+(.+)$", token)
        if one_line_match:
            j = i + 1
            name_parts = [one_line_match.group(2).strip()]
        elif _looks_like_hsn_code(token):
            j = i + 1
            name_parts = []
        else:
            i += 1
            continue

        while j < len(lines):
            t = lines[j].strip()
            l = t.lower()
            if not t:
                j += 1
                continue
            if _looks_like_hsn_code(t) or any(k in l for k in ("items:", "breakup", "amount received")):
                break
            if _looks_like_qty_token(t):
                break
            if any(k in l for k in ("cgst", "sgst", "igst")):
                break
            # Keep only sensible name chunks.
            if re.search(r"[A-Za-z]", t):
                name_parts.append(t)
            j += 1

        if not name_parts:
            i += 1
            continue

        if j >= len(lines):
            break

        qty_token = lines[j].strip()
        if not _looks_like_qty_token(qty_token):
            i += 1
            continue
        qty = _qty_from_token(qty_token)
        j += 1

        price_vals: List[float] = []
        while j < len(lines) and len(price_vals) < 3:
            t = lines[j].strip()
            l = t.lower()
            if not t:
                j += 1
                continue
            if re.fullmatch(r"\d+\)", t):
                # tax slab markers like "2)" / "3)"
                break
            if _looks_like_hsn_code(t) or any(k in l for k in ("items:", "breakup", "amount received", "cgst", "sgst")):
                break
            if re.search(r"[A-Za-z]", t):
                break
            if "%" in t:
                # tax marker rows sometimes leak into item block
                j += 1
                continue
            v = _to_float(t)
            if v is None:
                break
            price_vals.append(float(v))
            j += 1

        if not price_vals:
            i += 1
            continue

        unit_price = price_vals[0]
        expected_total = float(qty * unit_price)
        if len(price_vals) == 1:
            total_price = round(expected_total, 2)
        else:
            candidates = price_vals[1:]
            total_price = min(candidates, key=lambda v: abs(v - expected_total))
            if abs(total_price - expected_total) > max(10, expected_total * 0.35):
                # OCR drift: prefer arithmetic-consistent amount.
                total_price = round(expected_total, 2)

        if not (0 < qty <= 50 and 0 < unit_price <= 50_000 and 0 < total_price <= 500_000):
            i += 1
            continue

        name = " ".join(name_parts)
        name = re.sub(r"\s+", " ", name).strip(".-/ ")
        if len(name) < 2:
            i += 1
            continue

        item = {
            "product_name": name,
            "quantity": float(qty),
            "unit_price": float(unit_price),
            "total_price": float(total_price),
            "tax": 0.0,
        }
        print(f"   [hsn] accepted row -> {item}")
        items.append(item)
        i = j

    print(f"   [hsn] parsed items: {len(items)}")
    return items


def _parse_tabular_item_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parse receipts where OCR outputs rows as vertical tokens:
        NAME
        QTY
        RATE
        AMOUNT
    """
    items: List[Dict[str, Any]] = []

    # Detect table header first; if absent, bail out quickly.
    header_pos = {
        "name": None,
        "quantity": None,
        "rate": None,
        "amount": None,
    }
    scan_upto = min(len(lines), 35)
    for idx in range(scan_upto):
        low = lines[idx].strip().lower()
        if low in header_pos and header_pos[low] is None:
            header_pos[low] = idx

    if any(v is None for v in header_pos.values()):
        print("   [tabular] header not confidently detected, skip tabular mode")
        return items

    start = max(v for v in header_pos.values()) + 1
    print(f"   [tabular] header detected, scanning rows from index {start}")

    i = start
    while i < len(lines):
        name = lines[i].strip()
        low = name.lower()

        if not name:
            i += 1
            continue
        if _is_totals_line(name) or any(w in low for w in ("thank", "visit", "cash memo", "date", "time", "items")):
            print(f"   [tabular] stop at footer/summary line: '{name}'")
            break
        if _is_numeric_only_line(name):
            i += 1
            continue
        if not re.search(r"[A-Za-z]", name):
            i += 1
            continue

        # Expect next 2-3 numeric lines
        nums: List[float] = []
        j = i + 1
        while j < len(lines) and len(nums) < 3:
            candidate = lines[j].strip()
            if not candidate:
                j += 1
                continue
            if _is_totals_line(candidate):
                break
            if not _is_numeric_only_line(candidate):
                break
            n = _to_float(candidate)
            if n is not None:
                nums.append(n)
            j += 1

        if len(nums) >= 2:
            quantity = nums[0] if len(nums) >= 3 else 1.0
            unit_price = nums[-2]
            total_price = nums[-1]

            # Light sanity check for obvious OCR drift.
            if 0 < quantity <= 50 and 0 < unit_price <= 50_000 and 0 < total_price <= 500_000:
                item = {
                    "product_name": name.strip(".-/ "),
                    "quantity": float(quantity),
                    "unit_price": float(unit_price),
                    "total_price": float(total_price),
                    "tax": 0.0,
                }
                print(f"   [tabular] accepted row -> {item}")
                items.append(item)
                i = j
                continue

        i += 1

    print(f"   [tabular] parsed items: {len(items)}")
    return items


def _is_name_candidate(line: str) -> bool:
    raw = (line or "").strip()
    if len(raw) < 3:
        return False
    low = raw.lower()
    if low in {"item", "items", "qty.price amount", "qty", "rate", "amount", "mrp", "pack", "batch", "exp"}:
        return False
    if _is_totals_line(raw):
        return False
    if any(k in low for k in ("total qty", "sub total", "grand total", "net total", "amount received")):
        return False
    if any(k in low for k in _NON_ITEM_NAME_HINTS):
        return False
    if any(k in low for k in _MERCHANT_SKIP_WORDS):
        return False
    if low in {"amount", "rate", "qty", "description", "scription", "qly", "rale", "disc.amount"}:
        return False
    # Ignore long ID-heavy metadata rows.
    digit_count = len(re.findall(r"\d", raw))
    if digit_count >= 8 and not any(u in low for u in ("kg", "g", "gm", "ml", "ea", "pc")):
        return False
    if _is_numeric_only_line(raw):
        return False
    return bool(re.search(r"[A-Za-z]", raw))


def _is_numericish_token(line: str) -> bool:
    raw = (line or "").strip()
    if not raw:
        return False
    if raw in {"-", "—", "_"}:
        return True
    if re.fullmatch(r"[A-Za-z]", raw):
        # OCR often reads qty=1 as I/l and qty=2 as Z.
        return raw.lower() in {"i", "l", "z", "n"}
    return _to_float(raw) is not None


def _parse_qty_token(raw: str) -> Optional[float]:
    tok = (raw or "").strip().lower()
    if tok in {"i", "l"}:
        return 1.0
    if tok in {"z", "n"}:
        return 2.0
    val = _to_float(tok)
    if val is None:
        return None
    # Integer qty (restaurants/general items)
    if 0 < val <= 50 and abs(val - round(val)) < 0.05:
        return float(round(val))
    # Decimal qty (weighted grocery produce)
    if 0 < val <= 20:
        return float(val)
    return None


def _resolve_vertical_price_fields(number_tokens: List[str]) -> Optional[Dict[str, float]]:
    """
    Resolve qty/unit/total from OCR rows where columns are split into separate lines.
    Handles common patterns:
      [unit, total]
      [unit, qty, total]
      [total, unit]  (column order drift)
      [total, unit, qty]
    """
    if len(number_tokens) == 3:
        r0, r1, r2 = number_tokens[0], number_tokens[1], number_tokens[2]
        qv = _parse_qty_token(r0)
        if qv is None:
            alt = _to_float(r0)
            if alt is not None and 0 < alt <= 50:
                qv = float(alt)
        uv = _to_float(r1)
        tv = _to_float(r2)
        if qv is not None and uv is not None and tv is not None and uv > 0 and tv > 0:
            if abs(float(qv) * float(uv) - float(tv)) <= max(2.0, float(tv) * 0.04):
                return {
                    "quantity": float(qv),
                    "unit_price": float(uv),
                    "total_price": float(tv),
                }

    values: List[float] = []
    qty_candidates: List[float] = []

    for tok in number_tokens:
        qty_val = _parse_qty_token(tok)
        if qty_val is not None:
            qty_candidates.append(qty_val)
        val = _to_float(tok)
        if val is not None:
            values.append(float(val))

    if not values:
        return None

    # Keep duplicate money amounts (e.g. unit 140.00 and line total 140.00 are separate lines).
    work_vals: List[float] = values[:]

    if len(work_vals) == 1:
        only = work_vals[0]
        return {"quantity": 1.0, "unit_price": only, "total_price": only}

    # Primary: fit qty*unit ~= total.
    best: Optional[Tuple[float, float, float, float]] = None
    trial_qtys = qty_candidates[:] if qty_candidates else []
    if not trial_qtys:
        trial_qtys = [v for v in work_vals if 0 < v <= 20]
    if 1.0 not in trial_qtys:
        trial_qtys.append(1.0)

    for qty in trial_qtys:
        for unit in work_vals:
            for total in work_vals:
                if unit <= 0 or total <= 0:
                    continue
                expected = qty * unit
                diff = abs(expected - total)
                if best is None or diff < best[3]:
                    best = (qty, unit, total, diff)

    if best is not None:
        qty, unit, total, diff = best
        if abs(total - (qty * unit)) <= max(8.0, max(total, qty * unit) * 0.20):
            # Do not swap unit/total when qty < 1 (e.g. 0.1 * 440 = 44: total < unit is correct).
            if qty >= 0.999 and total < unit:
                unit, total = total, unit
            return {"quantity": float(qty), "unit_price": float(unit), "total_price": float(total)}

    # Conservative fallback.
    if len(work_vals) >= 2:
        low = min(work_vals)
        high = max(work_vals)
        return {"quantity": 1.0, "unit_price": float(low), "total_price": float(high)}

    return None


def _parse_vertical_menu_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parse receipts where item names and numeric columns are on separate lines.
    Example pattern:
        Buttermilk
        65.00
        4
        260.00
    """
    items: List[Dict[str, Any]] = []
    header_idx = _find_header_line_idx(lines, max_scan=80)
    i = header_idx + 1 if header_idx >= 0 else 0
    n = len(lines)

    print("   [vertical] scanning name + numeric token groups")

    while i < n:
        line = lines[i].strip()
        low = line.lower()

        if any(k in low for k in ("total qty", "sub total", "grand total", "net total", "amount received", "received amount", "payment details", "tax summary", "for queries", "visit again", "points")):
            print(f"   [vertical] stop at totals/footer line: '{line}'")
            break
        if ":" in line and not re.search(r"[A-Za-z]{4,}\s*-\s*[A-Za-z]{2,}", line):
            i += 1
            continue

        if not _is_name_candidate(line):
            i += 1
            continue

        # Merge consecutive name lines ("Garlic Ghee Roast" + "Dosa").
        name_parts = [line]
        j = i + 1
        while j < n and _is_name_candidate(lines[j].strip()):
            nxt = lines[j].strip()
            nxt_low = nxt.lower()
            if nxt_low in {"amount", "rate", "qty", "description", "scription", "qly", "rale", "disc.amount"}:
                j += 1
                continue
            if any(k in nxt_low for k in ("total qty", "sub total", "grand total", "net total")):
                break
            name_parts.append(nxt)
            j += 1

        name = " ".join(name_parts)
        name = re.sub(r"\s+", " ", name).strip(".-/ ")
        name_low = name.lower()
        if any(k in name_low for k in _NON_ITEM_NAME_HINTS):
            i = j if j > i else i + 1
            continue

        # Collect following numeric-like tokens until next name/footer.
        num_tokens: List[str] = []
        k = j
        while k < n and len(num_tokens) < 3:
            probe = lines[k].strip()
            probe_low = probe.lower()
            if any(x in probe_low for x in ("total qty", "sub total", "grand total", "net total", "amount received", "received amount", "payment details", "tax summary", "points", "for queries")):
                break
            if _is_name_candidate(probe):
                break
            if _is_numericish_token(probe):
                if probe not in {"-", "—", "_"}:
                    num_tokens.append(probe)
            k += 1

        if not num_tokens:
            i = j if j > i else i + 1
            continue

        fields = _resolve_vertical_price_fields(num_tokens)
        if not fields:
            i = k if k > i else i + 1
            continue

        qty = fields["quantity"]
        unit_price = fields["unit_price"]
        total_price = fields["total_price"]

        if not (0 < qty <= 50 and 0 < unit_price <= 50_000 and 0 < total_price <= 500_000):
            i = k if k > i else i + 1
            continue

        # Guard against metadata rows that still pass shape checks.
        if ":" in name and len(name.split()) <= 6:
            i = k if k > i else i + 1
            continue
        if qty == 1.0 and unit_price > 500 and any(k in name_low for k in ("upi", "tax", "disc", "invoice", "cashier", "address", "details")):
            i = k if k > i else i + 1
            continue

        item = {
            "product_name": name,
            "quantity": float(qty),
            "unit_price": float(unit_price),
            "total_price": float(total_price),
            "tax": 0.0,
        }
        print(f"   [vertical] accepted row -> {item}")
        items.append(item)
        i = k if k > i else i + 1

    print(f"   [vertical] parsed items: {len(items)}")
    return items


def _looks_like_item_line(line: str) -> bool:
    """
    Heuristic filter. Returns True if line is likely a purchased item.
    Now more permissive than the original – soft-skip words are only
    rejected when the line looks purely like a summary line.
    """
    raw = line.strip()
    low = raw.lower()

    print(f"\n   [filter] checking: '{raw}'")

    # ── too short
    if len(raw) < 5:
        print("      -> SKIP (too short)")
        return False

    # ── must contain at least one letter
    if not re.search(r"[A-Za-z]", raw):
        print("      -> SKIP (no letters)")
        return False

    # ── hard-skip words
    for w in _SKIP_WORDS:
        if w in low:
            print(f"      -> SKIP (hard-skip word '{w}')")
            return False

    # ── number count: item lines usually have 1-6 numeric tokens
    nums = _extract_number_tokens(raw)
    if not (1 <= len(nums) <= 6):
        print(f"      -> SKIP (number count {len(nums)} not in [1,6])")
        return False

    # ── soft-skip: reject only if the line is *purely* a totals line
    #    (i.e. the non-numeric, non-punctuation text is just a total-word)
    alpha_words = [w for w in re.findall(r"[A-Za-z]+", raw) if len(w) > 1]
    all_soft = all(w.lower() in _SOFT_SKIP_WORDS for w in alpha_words)
    if all_soft:
        print(f"      -> SKIP (purely a totals/summary line: {alpha_words})")
        return False

    print("      -> PASS")
    return True


# ──────────────────────────────────────────────
# ITEM PARSER
# ──────────────────────────────────────────────

def _parse_item_from_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Try to extract (name, qty, unit_price, total_price) from one line.

    Column assumption (right-to-left):
        last  number  = total_price
        2nd-last      = unit_price
        3rd-last      = quantity  (optional; default 1)
    """
    print(f"\n   [parser] '{line}'")
    nums = _extract_number_tokens(line)

    values: List[Tuple[float, int, int]] = []
    for tok, s, e in nums:
        val = _to_float(tok)
        if val is not None:
            values.append((val, s, e))

    if len(values) < 1:
        print(f"      -> REJECT (fewer than 1 parsed values)")
        return None

    if len(values) == 1:
        # Some receipts only show a single amount in item rows.
        total_price = values[-1][0]
        unit_price = total_price
        quantity = 1.0
    else:
        total_price = values[-1][0]
        unit_price = values[-2][0]
        quantity = values[-3][0] if len(values) >= 3 else 1.0

    print(f"      qty={quantity}  unit={unit_price}  total={total_price}")

    # ── sanity guards
    if not (0 < quantity <= 50):
        print(f"      -> REJECT (qty {quantity} out of range 0-50)")
        return None
    if not (0 < unit_price <= 50_000):
        print(f"      -> REJECT (unit_price {unit_price} out of range)")
        return None
    if not (0 < total_price <= 500_000):
        print(f"      -> REJECT (total_price {total_price} out of range)")
        return None

    # math check: total ≈ qty × unit (skip when there is only one value)
    if len(values) >= 2:
        expected = quantity * unit_price
        tolerance = max(10, total_price * 0.35)
        if abs(expected - total_price) > tolerance:
            print(
                f"      -> REJECT (math mismatch: {quantity}*{unit_price}="
                f"{expected:.2f} vs total {total_price}, diff={abs(expected-total_price):.2f})"
            )
            return None

    # ── extract product name (everything left of the quantity column)
    if len(values) >= 3:
        cut = values[-3][1]
    elif len(values) >= 2:
        cut = values[-2][1]
    else:
        cut = values[-1][1]
    name = line[:cut].strip()
    name = re.sub(r"\s+", " ", name)
    name = name.strip(".-/ ")

    print(f"      raw name: '{name}'")

    if len(name) < 2:
        print("      -> REJECT (name too short)")
        return None
    if len(name.split()) > 12:
        print(f"      -> REJECT (name too many words: {len(name.split())})")
        return None

    item = {
        "product_name": name,
        "quantity":     float(quantity),
        "unit_price":   float(unit_price),
        "total_price":  float(total_price),
        "tax":          0.0,
    }
    print(f"      -> ACCEPT {item}")
    return item


# ──────────────────────────────────────────────
# TOTAL EXTRACTOR


def _extract_total(lines: List[str]) -> float:
    """
    Scan lines in reverse for a 'total' line and grab the last number.
    Tries several keywords in priority order.
    """
    keywords = [
        "amount received from customer", "received amount", "card payment", "cash payment",
        "gross sale value", "net payable", "grand total", "net total", "net amount", "total amount", "sub total", "total", "ttal",
    ]
    print("\n   [total] scanning for total line ...")

    for kw in keywords:
        for idx in range(len(lines) - 1, -1, -1):
            ln = lines[idx]
            if kw in ln.lower():
                low_ln = ln.lower()
                if kw in {"total", "sub total"} and any(bad in low_ln for bad in ("discount", "qty", "tax summary", "cgst", "sgst", "points", "items:")):
                    continue
                nums = _extract_number_tokens(ln)
                if nums:
                    val = _to_float(nums[-1][0])
                    if val and val > 0:
                        print(f"   [total] found via '{kw}' -> {val}  (line: '{ln}')")
                        return val
                # Handle split layout:
                #   "Total :" on one line and amount on next line.
                for nxt in range(idx + 1, min(idx + 4, len(lines))):
                    look = lines[nxt]
                    low_look = look.lower()
                    if "%" in look or any(bad in low_look for bad in ("discount", "cgst", "sgst", "tax summary", "points", "items:")):
                        continue
                    look_nums = _extract_number_tokens(look)
                    if not look_nums:
                        continue
                    val = _to_float(look_nums[-1][0])
                    if val and val > 0:
                        print(
                            f"   [total] found via '{kw}' on following line -> {val} "
                            f"(lines: '{ln}' / '{look}')"
                        )
                        return val
    print("   [total] not found, will fall back to item sum")
    return 0.0


# ──────────────────────────────────────────────
# MAIN ENTRY
# ──────────────────────────────────────────────

def parse_receipt(ocr_input: Union[List[str], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse a list of OCR text lines into structured receipt data.

    Args:
        lines: Raw OCR output lines (list of strings).

    Returns:
        {
            "items": [...],
            "total_amount": float,
            "merchant": str,       ← first non-empty line heuristic
            "raw_line_count": int, ← debug
        }
    """
    lines: List[str]
    tokens: List[Dict[str, Any]]
    if isinstance(ocr_input, dict):
        lines = [str(x) for x in (ocr_input.get("lines") or [])]
        raw_tokens = ocr_input.get("tokens") or []
        tokens = [t for t in raw_tokens if isinstance(t, dict)]
    else:
        lines = [str(x) for x in (ocr_input or [])]
        tokens = []

    lines = _expand_glued_numeric_ocr_lines(lines)

    # Optional semantic parse first (Ollama). Requires RECEIPT_LLM_MODE=always and a running model.
    if _llm_rp.is_llm_enabled() and _llm_rp.llm_mode() == "always":
        llm_first = _llm_rp.parse_receipt_llm(lines)
        if _llm_rp.llm_result_usable(llm_first):
            print("\n" + "="*60)
            print("[RECEIPT PARSER] LLM-first path (RECEIPT_LLM_MODE=always)")
            print(f"    items={len(llm_first.get('items') or [])} total={llm_first.get('total_amount')}")
            print("="*60 + "\n")
            return llm_first

    print("\n" + "="*60)
    print("[RECEIPT PARSER] START")
    print(f"    Input: {len(lines)} lines")
    if tokens:
        print(f"    OCR tokens with coordinates: {len(tokens)}")
    print("="*60)

    for i, ln in enumerate(lines):
        print(f"  [{i:03d}] {ln}")

    print("="*60)

    # ── merchant heuristic: first substantive line (skip duplicate stamps / address-only)
    merchant = ""
    for ln in lines[:22]:
        low = ln.lower().strip(". ")
        if any(low.startswith(p) for p in _MERCHANT_NOISE_PREFIXES):
            continue
        if any(w in low for w in _MERCHANT_SKIP_WORDS):
            continue
        if re.search(r"[A-Za-z]{3,}", ln) and not re.search(r"\d{6,}", ln):
            merchant = ln.strip()
            print(f"\n   [merchant] heuristic -> '{merchant}'")
            break
    if not merchant:
        for ln in lines[:30]:
            low = ln.lower()
            if any(k in low for k in ("pvt", "ltd", "medical", "medicos", "retail", "store", "supermarket", "sweets")):
                merchant = ln.strip()
                print(f"\n   [merchant] keyword fallback -> '{merchant}'")
                break

    # ── parse items (try specialised table modes first, then fallback line parser)
    items: List[Dict[str, Any]] = _parse_coord_table_rows(tokens) if tokens else []
    if not items:
        items = _parse_hsn_item_rows(lines)
    if not items:
        items = _parse_tabular_item_rows(lines)
    if not items:
        items = _parse_vertical_menu_rows(lines)
    skipped = 0

    if not items:
        for ln in lines:
            if not _looks_like_item_line(ln):
                skipped += 1
                continue

            item = _parse_item_from_line(ln)
            if item:
                items.append(item)
            else:
                skipped += 1

    # ── total
    total = _extract_total(lines)
    if total <= 0 and items:
        total = round(sum(i["total_price"] for i in items), 2)
        print(f"\n   [total] fallback -> sum of items = {total}")

    result: Dict[str, Any] = {
        "merchant":       merchant,
        "items":          items,
        "total_amount":   total,
        "raw_line_count": len(lines),
        "parse_source":   "heuristic",
    }

    # If heuristics look weak, try LLM (RECEIPT_LLM_MODE=fallback).
    if (
        _llm_rp.is_llm_enabled()
        and _llm_rp.llm_mode() == "fallback"
        and _llm_rp.heuristic_looks_weak(result, lines)
    ):
        llm_try = _llm_rp.parse_receipt_llm(lines)
        if (
            llm_try
            and _llm_rp.llm_result_usable(llm_try)
            and _llm_rp.llm_preferred_over_heuristic(llm_try, result)
        ):
            llm_try["parse_source"] = "llm_fallback"
            print("\n" + "="*60)
            print(
                "[RECEIPT PARSER] LLM fallback replaced heuristic "
                f"(items {len(result.get('items') or [])} -> {len(llm_try.get('items') or [])})"
            )
            print("="*60 + "\n")
            print(llm_try)
            return llm_try

    print("\n" + "="*60)
    print(f"[RECEIPT PARSER] DONE - {len(items)} items, total={total}, skipped={skipped}")
    print("="*60 + "\n")
    print(result)
    return result
