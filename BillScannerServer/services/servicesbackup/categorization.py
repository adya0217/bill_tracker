"""
services/categorization.py

Item category prediction.  Uses the trained scikit-learn pipeline
(category_model.pkl) when available, then falls back to keyword matching.

─── HOW TO UPDATE THE MODEL ───────────────────────────────────────────
1. Open train_categorizer.py in Google Colab
2. Add more training samples (especially real OCR data you've collected)
3. Run all cells → download category_model.pkl
4. Place the new .pkl here:  backend/services/category_model.pkl
5. Restart the FastAPI server — new model loads automatically
────────────────────────────────────────────────────────────────────────
"""

import os
import re
import pickle
import logging
from typing import Optional

log = logging.getLogger("categorization")

# ──────────────────────────────────────────────
# MODEL PATH
# ──────────────────────────────────────────────

MODEL_PATH = os.path.join(os.path.dirname(__file__), "category_model.pkl")
_model = None   # module-level cache — loaded once, reused forever


# ──────────────────────────────────────────────
# KEYWORD FALLBACK
# ──────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Groceries": [
        "milk", "atta", "rice", "dal", "egg", "oil", "sugar", "flour",
        "wheat", "salt", "masala", "paneer", "ghee", "besan", "curd",
        "butter", "bread", "poha", "rava", "semolina", "onion", "potato",
        "tomato", "vegetable", "fruit", "pickle", "chilli", "turmeric",
        "coriander", "garam", "toor", "chana", "moong",
    ],
    "Household": [
        "soap", "detergent", "shampoo", "cleaner", "brush", "tissue",
        "mop", "phenyl", "broom", "dishwash", "vim", "harpic", "lizol",
        "toothpaste", "toothbrush", "scrub", "coil", "mosquito", "dettol",
        "gillette", "shaving", "floor", "toilet", "washing powder",
    ],
    "Medical": [
        "tablet", "medicine", "capsule", "syrup", "ointment", "vitamin",
        "paracetamol", "strip", "cream", "drops", "injection", "bandaid",
        "ors", "sachet", "spray", "antiseptic", "crocin", "dolo", "combiflam",
        "pan40", "gelusil", "glucon", "burnol", "betadine", "disprin",
        "cetirizine",
    ],
    "Electronics": [
        "charger", "cable", "usb", "adapter", "battery", "headphone",
        "earphone", "wire", "bulb", "led", "hdmi", "sd card", "mouse",
        "keyboard", "hub", "cooling", "otg", "screen protector", "cover",
        "case", "bluetooth",
    ],
    "Dining": [
        "biryani", "dosa", "idli", "vada", "pav", "thali", "pizza",
        "burger", "coffee", "cappuccino", "chai", "lassi", "chole",
        "bhature", "paneer", "naan", "roti", "combo", "meal", "plate",
    ],
    "Beverages": [
        "cola", "pepsi", "coke", "sprite", "thums up", "frooti", "maaza",
        "juice", "water", "bisleri", "kinley", "red bull", "coconut water",
        "nimbu", "buttermilk", "amul kool",
    ],
    "Snacks": [
        "chips", "lays", "kurkure", "namkeen", "bhujia", "biscuit",
        "parle", "bourbon", "kitkat", "dairy milk", "chocolate", "oreo",
        "popcorn", "wafer", "pringles", "mixture", "too yumm",
    ],
}


def _keyword_category(name: str) -> str:
    lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            log.debug(f"[keyword] '{name}' → '{category}'")
            return category
    log.debug(f"[keyword] '{name}' → 'Other' (no match)")
    return "Other"


# ──────────────────────────────────────────────
# MODEL LOADER
# ──────────────────────────────────────────────

def _load_model():
    global _model
    if _model is not None:
        return _model

    if not os.path.exists(MODEL_PATH):
        log.info(f"[categorize] No model at '{MODEL_PATH}' — using keyword fallback")
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        log.info(f"[categorize] ✅ ML model loaded from '{MODEL_PATH}'")
        return _model
    except Exception as exc:
        log.warning(f"[categorize] ⚠️  Failed to load model: {exc} — using keywords")
        _model = None
        return None


# ──────────────────────────────────────────────
# PRE-PROCESSING
# ──────────────────────────────────────────────

def _preprocess(name: str) -> str:
    """
    Normalise item names before prediction.
    Keeps OCR digit-substitutions (1, 0, 3 …) intact because the
    char n-gram model was trained on those patterns.
    """
    text = name.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # drop punctuation
    text = re.sub(r"\s+",     " ", text)    # normalise spaces
    return text.strip()


# ──────────────────────────────────────────────
# PUBLIC API — single item
# ──────────────────────────────────────────────

def categorize_item(name: str) -> str:
    """
    Predict category for a single product name.

    Priority:
        1. ML model  (if trained .pkl exists)
        2. Keyword table  (always available as fallback)

    Returns one of:
        Groceries | Household | Medical | Electronics |
        Dining | Beverages | Snacks | Other
    """
    clean = _preprocess(name or "")

    if not clean:
        return "Other"

    model = _load_model()

    if model is not None:
        try:
            pred = model.predict([clean])[0]
            conf = float(model.predict_proba([clean]).max())
            log.debug(f"[categorize] ML: '{clean}' → '{pred}'  conf={conf:.2f}")

            # Low-confidence ML prediction: let keywords override if they match
            if conf < 0.40:
                kw = _keyword_category(clean)
                if kw != "Other":
                    log.debug(f"[categorize] low conf ({conf:.2f}) → keyword '{kw}'")
                    return kw

            return str(pred)

        except Exception as exc:
            log.warning(f"[categorize] ML predict failed ({exc}) — falling back")

    return _keyword_category(clean)


# ──────────────────────────────────────────────
# PUBLIC API — batch
# ──────────────────────────────────────────────

def categorize_items(names: list[str]) -> list[str]:
    """
    Batch categorisation — single model.predict() call for all items.
    Use this in the bills router instead of looping over categorize_item().
    """
    if not names:
        return []

    model   = _load_model()
    cleaned = [_preprocess(n or "") for n in names]

    if model is not None:
        try:
            preds = model.predict(cleaned)
            probs = model.predict_proba(cleaned).max(axis=1)

            results = []
            for name, pred, conf in zip(cleaned, preds, probs):
                if conf < 0.40:
                    kw = _keyword_category(name)
                    results.append(kw if kw != "Other" else str(pred))
                else:
                    results.append(str(pred))
            return results
        except Exception as exc:
            log.warning(f"[categorize_items] batch predict failed ({exc})")

    return [_keyword_category(n) for n in cleaned]


# ──────────────────────────────────────────────
# RETRAINING FROM DB
# ──────────────────────────────────────────────

def train_category_model(db) -> int:
    """
    Retrain the model from labelled BillItems already in the database.
    Call via a management endpoint after manually correcting categories.
    Returns number of training samples used (0 if skipped).
    """
    try:
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        log.warning("[train] scikit-learn not installed — cannot retrain")
        return 0

    try:
        from models.bill_item import BillItem
        from models.category  import Category
    except ImportError:
        log.warning("[train] models not importable")
        return 0

    log.info("[train] Querying labelled BillItems from DB …")
    rows = (
        db.query(BillItem.product_name, Category.name)
        .join(Category, BillItem.category_id == Category.id)
        .filter(BillItem.product_name.isnot(None))
        .all()
    )

    if len(rows) < 10:
        log.warning(f"[train] Only {len(rows)} samples — need ≥10, skipping")
        return 0

    texts  = [_preprocess(r[0]) for r in rows]
    labels = [r[1]              for r in rows]

    from collections import Counter
    log.info(f"[train] Label distribution: {dict(Counter(labels))}")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3), min_df=1, max_features=8000,
            analyzer="char_wb", sublinear_tf=True,
        )),
        ("clf", LogisticRegression(max_iter=2000, C=5.0, solver="lbfgs")),
    ])

    pipeline.fit(texts, labels)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)

    global _model
    _model = pipeline
    log.info(f"[train] ✅ Saved → '{MODEL_PATH}'  ({len(texts)} samples)")
    return len(texts)


# ──────────────────────────────────────────────
# QUICK SELF-TEST
# Run: python -m services.categorization
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)-8s %(message)s")

    TEST = [
        # clean text
        ("amul milk 500ml",      "Groceries"),
        ("dolo 650 tablet",      "Medical"),
        ("usb type c cable",     "Electronics"),
        ("lays chips masala",    "Snacks"),
        ("bisleri water 500ml",  "Beverages"),
        ("dove soap bar",        "Household"),
        ("chicken biryani",      "Dining"),
        # OCR noise
        ("amu1 m1lk",            "Groceries"),
        ("d0l0 650",             "Medical"),
        ("u5b cab1e",            "Electronics"),
        ("3ggs tray 30",         "Groceries"),
        ("b1scu1t parle g",      "Snacks"),
        # edge cases
        ("",                     "Other"),
        ("xyz123",               "Other"),
    ]

    print(f"\n{'Item':<35} {'Expected':<15} {'Got':<15} {'Match'}")
    print("-" * 72)
    ok = 0
    for item, expected in TEST:
        got   = categorize_item(item)
        match = "✅" if got == expected else "❌"
        if got == expected:
            ok += 1
        print(f"{item or '(empty)':<35} {expected:<15} {got:<15} {match}")

    print(f"\nScore: {ok}/{len(TEST)}")
    print(f"Model file present: {os.path.exists(MODEL_PATH)}")