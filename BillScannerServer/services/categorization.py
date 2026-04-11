"""
categorization.py  –  item category prediction

Priority:
    1. Trained scikit-learn pipeline  (if model file exists)
    2. Keyword lookup table           (always available)

scikit-learn is optional: the module degrades gracefully if it's not installed.
"""

import os
import pickle
from typing import Optional

from sqlalchemy.orm import Session

from models.bill_item import BillItem
from models.category import Category

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    _SKLEARN_AVAILABLE = True
    print("[categorization] scikit-learn ✓")
except Exception:
    TfidfVectorizer    = None   # type: ignore
    LogisticRegression = None   # type: ignore
    Pipeline           = None   # type: ignore
    _SKLEARN_AVAILABLE = False
    print("[categorization] scikit-learn not installed – keyword fallback only")


# ──────────────────────────────────────────────
# KEYWORD TABLE
# ──────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Groceries": [
        "milk", "bread", "rice", "atta", "dal", "egg", "vegetable", "veggie",
        "fruit", "curd", "butter", "cheese", "oil", "sugar", "flour", "wheat",
        "salt", "spice", "masala", "paneer", "ghee", "besan",
    ],
    "Household": [
        "soap", "detergent", "shampoo", "cleaner", "brush", "tissue", "mop",
        "phenyl", "broom", "dishwash", "vim", "harpic", "floor",
    ],
    "Medical": [
        "tablet", "medicine", "capsule", "syrup", "ointment", "vitamin",
        "paracetamol", "strip", "cream", "drops", "injection",
    ],
    "Electronics": [
        "charger", "cable", "usb", "adapter", "battery", "headphone",
        "earphone", "wire", "bulb", "led",
    ],
    "Dining": [
        "pizza", "burger", "coffee", "tea", "meal", "combo", "thali",
        "sandwich", "biryani", "juice", "water", "bottle",
    ],
    "Beverages": [
        "cola", "pepsi", "coke", "sprite", "fanta", "soda", "lassi",
        "nimbu", "coconut water",
    ],
    "Snacks": [
        "chips", "biscuit", "namkeen", "mixture", "wafer", "kurkure",
        "chocolate", "candy",
    ],
}


# ──────────────────────────────────────────────
# MODEL PATH
# ──────────────────────────────────────────────

MODEL_PATH = os.path.join(os.path.dirname(__file__), "category_model.pkl")
_model: Optional[object] = None   # cached Pipeline


# ──────────────────────────────────────────────
# KEYWORD FALLBACK
# ──────────────────────────────────────────────

def _keyword_category(name: str) -> str:
    lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                print(f"[categorize] keyword match: '{name}' → '{category}'  (kw='{kw}')")
                return category
    print(f"[categorize] no keyword match for '{name}' → 'Other'")
    return "Other"


# ──────────────────────────────────────────────
# MODEL LOADER
# ──────────────────────────────────────────────

def _load_model() -> Optional[object]:
    global _model
    if _model is not None:
        return _model

    if not os.path.exists(MODEL_PATH):
        print(f"[categorize] No model file at '{MODEL_PATH}' – using keywords")
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        print(f"[categorize] ML model loaded from '{MODEL_PATH}'")
        return _model
    except Exception as exc:
        print(f"[categorize] ⚠️  Failed to load model: {exc}")
        _model = None
        return None


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────

def categorize_item(name: str) -> str:
    """
    Predict the category for a product name.

    Returns one of the keys in CATEGORY_KEYWORDS or "Other".
    """
    clean = (name or "").strip()
    if not clean:
        print("[categorize] empty name → 'Other'")
        return "Other"

    model = _load_model()
    if model:
        try:
            pred = model.predict([clean])[0]
            print(f"[categorize] ML model: '{clean}' → '{pred}'")
            return str(pred)
        except Exception as exc:
            print(f"[categorize] ⚠️  ML predict failed ({exc}) – falling back to keywords")

    return _keyword_category(clean)


# ──────────────────────────────────────────────
# TRAINING
# ──────────────────────────────────────────────

def train_category_model(db: Session) -> int:
    """
    Train a TF-IDF + LogisticRegression classifier from labelled BillItems in DB.

    Returns the number of training samples used (0 if training was skipped).
    """
    if not _SKLEARN_AVAILABLE:
        print("[train] scikit-learn not installed – cannot train")
        return 0

    print("[train] Querying labelled items from DB …")
    rows = (
        db.query(BillItem.product_name, Category.name)
        .join(Category, BillItem.category_id == Category.id)
        .filter(BillItem.product_name.isnot(None))
        .all()
    )

    print(f"[train] Found {len(rows)} labelled rows")

    if not rows or len(rows) < 5:
        print("[train] ⚠️  Not enough labelled data (need ≥5) – skipping")
        return 0

    texts  = [r[0] for r in rows]
    labels = [r[1] for r in rows]

    # Label distribution
    from collections import Counter
    dist = Counter(labels)
    print(f"[train] Label distribution: {dict(dist)}")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf",   LogisticRegression(max_iter=1000)),
    ])

    print("[train] Fitting pipeline …")
    pipeline.fit(texts, labels)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)

    global _model
    _model = pipeline

    print(f"[train] ✅ Model saved to '{MODEL_PATH}'  ({len(texts)} samples)")
    return len(texts)
