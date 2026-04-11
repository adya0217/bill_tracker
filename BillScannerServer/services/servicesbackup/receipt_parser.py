import re
from typing import Any, Dict, List, Optional, Tuple

NumberToken = Tuple[str, int, int]


# ---------------- NUMBER ---------------- #

def _to_float(tok: str) -> Optional[float]:
    try:
        tok = tok.strip()

        if re.match(r"^\d+\.000$", tok):
            return float(tok.split(".")[0])

        if "," in tok and "." not in tok:
            return float(tok.replace(",", ""))

        return float(tok)
    except:
        return None


def _extract_number_tokens(line: str) -> List[NumberToken]:
    matches = list(re.finditer(r"\d+(?:[.,]\d+)?", line))
    return [(m.group(0), m.start(), m.end()) for m in matches]


# ---------------- FILTERS ---------------- #

def _looks_like_item_line(line: str) -> bool:
    if len(line) < 6:
        return False

    if not re.search(r"[A-Za-z]", line):
        return False

    nums = _extract_number_tokens(line)

    if not (2 <= len(nums) <= 4):
        return False

    bad_words = [
        "gst", "bill", "invoice", "date", "time",
        "total", "amount", "phone", "no:", "cin",
        "tax", "rate", "cash"
    ]

    low = line.lower()
    if any(k in low for k in bad_words):
        return False

    return True


# ---------------- PARSER ---------------- #

def _parse_item_from_line(line: str) -> Optional[Dict[str, Any]]:
    nums = _extract_number_tokens(line)

    values = []
    for tok, s, e in nums:
        val = _to_float(tok)
        if val is not None:
            values.append((val, s, e))

    if len(values) < 2:
        return None

    try:
        total_price = values[-1][0]
        unit_price = values[-2][0]
        quantity = values[-3][0] if len(values) >= 3 else 1.0
    except IndexError:
        return None

    # sanity checks
    if not (0 < quantity <= 20):
        return None
    if not (0 < unit_price <= 10000):
        return None
    if not (0 < total_price <= 100000):
        return None

    expected = quantity * unit_price

    if abs(expected - total_price) > max(5, total_price * 0.3):
        print("❌ MISMATCH REJECT:", line)
        return None

    cut = values[-3][1] if len(values) >= 3 else values[-2][1]
    name = line[:cut].strip()
    name = re.sub(r"\s+", " ", name)

    if len(name) < 3 or len(name.split()) > 6:
        return None

    return {
        "product_name": name,
        "quantity": float(quantity),
        "unit_price": float(unit_price),
        "total_price": float(total_price),
        "tax": 0.0,
    }


# ---------------- TOTAL ---------------- #

def _extract_total(lines: List[str]) -> float:
    for ln in reversed(lines):
        if "total" in ln.lower():
            nums = _extract_number_tokens(ln)
            if nums:
                val = _to_float(nums[-1][0])
                if val:
                    return val
    return 0.0


# ---------------- MAIN ---------------- #

def parse_receipt(lines: List[str]) -> Dict[str, Any]:
    print("\n🔍 PARSING START")

    items = []

    for ln in lines:
        if not _looks_like_item_line(ln):
            continue

        print("👉", ln)

        item = _parse_item_from_line(ln)

        if item:
            print("   ✅", item)
            items.append(item)
        else:
            print("   ❌ rejected")

    total = _extract_total(lines)

    if total <= 0 and items:
        total = sum(i["total_price"] for i in items)
        print("⚠️ fallback total:", total)

    result = {
        "items": items,
        "total_amount": total
    }

    print("\n✅ FINAL RESULT:", result)
    return result