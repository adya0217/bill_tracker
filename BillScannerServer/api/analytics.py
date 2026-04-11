from typing import Dict, Any, List, Tuple

from fastapi import APIRouter

from database import SessionLocal
from models.bill import Bill
from models.bill_item import BillItem
from models.category import Category
from models.vendor import Vendor
from services.categorization import train_category_model


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
@router.get("/summary/{device_id}")
def analytics_summary(device_id: str) -> Dict[str, Any]:
    """
    High-level analytics for a device:
    - total spend
    - bill count
    - spend per category
    """
    db = SessionLocal()
    try:
        bills = db.query(Bill).filter(Bill.device_id == device_id).all()
        bill_ids = [b.id for b in bills]

        bill_count = len(bills)
        if not bill_ids:
            return {
                "device_id": device_id,
                "total_spend": 0.0,
                "bill_count": 0,
                "by_category": [],
                "by_store": [],
                "by_day": [],
                "by_month": [],
                "by_year": [],
            }

        # Build category totals from items; if total_price is missing, fall back to qty*unit_price.
        item_rows: List[Tuple[str, float, float, float]] = (
            db.query(Category.name, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
            .join(BillItem, BillItem.category_id == Category.id)
            .filter(BillItem.bill_id.in_(bill_ids))
            .all()
        )

        by_cat: Dict[str, float] = {}
        for name, total_price, qty, unit_price in item_rows:
            computed = float(total_price or 0)
            if computed <= 0:
                computed = float((qty or 0) * (unit_price or 0))
            by_cat[name] = by_cat.get(name, 0.0) + computed

        by_category = [
            {"category": name, "total_spend": value} for name, value in by_cat.items()
        ]

        # Total spend: prefer bill.total_amount, but if it's 0, fall back to sum of item totals for that bill.
        per_bill_totals: Dict[int, float] = {}
        per_bill_item_rows = (
            db.query(BillItem.bill_id, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
            .filter(BillItem.bill_id.in_(bill_ids))
            .all()
        )
        for bill_id, total_price, qty, unit_price in per_bill_item_rows:
            computed = float(total_price or 0)
            if computed <= 0:
                computed = float((qty or 0) * (unit_price or 0))
            per_bill_totals[bill_id] = per_bill_totals.get(bill_id, 0.0) + computed

        total_spend = 0.0
        for b in bills:
            bill_total = float(b.total_amount or 0)
            if bill_total <= 0:
                bill_total = per_bill_totals.get(b.id, 0.0)
            total_spend += bill_total

        summary = {
            "device_id": device_id,
            "total_spend": total_spend,
            "bill_count": bill_count,
            "by_category": by_category,
        }
        summary["by_store"] = analytics_by_store(device_id).get("by_store", [])
        summary["by_day"] = analytics_by_day(device_id).get("by_day", [])
        summary["by_month"] = analytics_monthly(device_id).get("by_month", [])
        summary["by_year"] = analytics_by_year(device_id).get("by_year", [])
        return summary

    finally:
        db.close()





@router.get("/by-store")
def analytics_by_store(device_id: str) -> Dict[str, Any]:
    """
    Spend per merchant / area for a device.
    """
    db = SessionLocal()
    try:
        bill_rows = (
            db.query(Bill, Vendor)
            .join(Vendor, Bill.vendor_id == Vendor.id)
            .filter(Bill.device_id == device_id)
            .all()
        )
        bill_ids = [b.id for (b, _) in bill_rows]

        per_bill_totals: Dict[int, float] = {}
        if bill_ids:
            per_bill_item_rows = (
                db.query(BillItem.bill_id, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
                .filter(BillItem.bill_id.in_(bill_ids))
                .all()
            )
            for bill_id, total_price, qty, unit_price in per_bill_item_rows:
                computed = float(total_price or 0)
                if computed <= 0:
                    computed = float((qty or 0) * (unit_price or 0))
                per_bill_totals[bill_id] = per_bill_totals.get(bill_id, 0.0) + computed

        by_store: Dict[str, float] = {}
        for b, v in bill_rows:
            store_name = v.vendor_name or "Unknown"
            # Optional: include city to make "store/area" more informative.
            if getattr(v, "city", None):
                store_name = f"{store_name} ({v.city})"

            bill_total = float(b.total_amount or 0)
            if bill_total <= 0:
                bill_total = per_bill_totals.get(b.id, 0.0)

            by_store[store_name] = by_store.get(store_name, 0.0) + bill_total

        stores = [
            {"store": name, "total_spend": value} for name, value in by_store.items()
        ]

        return {"device_id": device_id, "by_store": stores}
    finally:
        db.close()


@router.get("/monthly")
@router.get("/by-month")
def analytics_monthly(device_id: str) -> Dict[str, Any]:
    """
    Monthly spending summary.    
    """
    db = SessionLocal()
    try:
        bills = db.query(Bill).filter(Bill.device_id == device_id).all()
        by_month: Dict[str, Dict[str, Any]] = {}

        bill_ids = [b.id for b in bills]
        per_bill_totals: Dict[int, float] = {}
        if bill_ids:
            per_bill_item_rows = (
                db.query(BillItem.bill_id, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
                .filter(BillItem.bill_id.in_(bill_ids))
                .all()
            )
            for bill_id, total_price, qty, unit_price in per_bill_item_rows:
                computed = float(total_price or 0)
                if computed <= 0:
                    computed = float((qty or 0) * (unit_price or 0))
                per_bill_totals[bill_id] = per_bill_totals.get(bill_id, 0.0) + computed

        for b in bills:
            if b.bill_date:
                s = str(b.bill_date)
                month_key = s[:7] if "-" in s and len(s) >= 7 else s
                if "/" in s:
                    parts = s.split("/")
                    if len(parts) == 3:
                        # Assume DD/MM/YYYY
                        day, month, year = parts
                        if len(month) == 1:
                            month = month.zfill(2)
                        month_key = f"{year}-{month}"
            else:
                month_key = b.created_at.strftime("%Y-%m") if b.created_at else "unknown"

            bill_total = float(b.total_amount or 0)
            if bill_total <= 0:
                bill_total = per_bill_totals.get(b.id, 0.0)

            bucket = by_month.setdefault(
                month_key, {"month": month_key, "total_spend": 0.0, "bill_count": 0}
            )
            bucket["total_spend"] += bill_total
            bucket["bill_count"] += 1

        months = sorted(by_month.values(), key=lambda x: x["month"])

        return {"device_id": device_id, "by_month": months}
    finally:
        db.close()


@router.get("/by-day")
def analytics_by_day(device_id: str) -> Dict[str, Any]:
    """
    Daily spending summary.
    
    """
    db = SessionLocal()
    try:
        bills = db.query(Bill).filter(Bill.device_id == device_id).all()
        bill_ids = [b.id for b in bills]

        per_bill_totals: Dict[int, float] = {}
        if bill_ids:
            per_bill_item_rows = (
                db.query(BillItem.bill_id, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
                .filter(BillItem.bill_id.in_(bill_ids))
                .all()
            )
            for bill_id, total_price, qty, unit_price in per_bill_item_rows:
                computed = float(total_price or 0)
                if computed <= 0:
                    computed = float((qty or 0) * (unit_price or 0))
                per_bill_totals[bill_id] = per_bill_totals.get(bill_id, 0.0) + computed

        by_day: Dict[str, Dict[str, Any]] = {}
        for b in bills:
            date_key = str(b.bill_date) if b.bill_date else (b.created_at.strftime("%Y-%m-%d") if b.created_at else "unknown")

            bill_total = float(b.total_amount or 0)
            if bill_total <= 0:
                bill_total = per_bill_totals.get(b.id, 0.0)

            bucket = by_day.setdefault(
                date_key, {"date": date_key, "total_spend": 0.0, "bill_count": 0}
            )
            bucket["total_spend"] += bill_total
            bucket["bill_count"] += 1

        days = sorted(by_day.values(), key=lambda x: x["date"])
        return {"device_id": device_id, "by_day": days}
    finally:
        db.close()


@router.get("/by-year")
def analytics_by_year(device_id: str) -> Dict[str, Any]:
    """
    Yearly spending summary for the mobile UI.
    Returns {year, total_spend, bill_count}
    """
    db = SessionLocal()
    try:
        bills = db.query(Bill).filter(Bill.device_id == device_id).all()
        bill_ids = [b.id for b in bills]

        per_bill_totals: Dict[int, float] = {}
        if bill_ids:
            per_bill_item_rows = (
                db.query(BillItem.bill_id, BillItem.total_price, BillItem.quantity, BillItem.unit_price)
                .filter(BillItem.bill_id.in_(bill_ids))
                .all()
            )
            for bill_id, total_price, qty, unit_price in per_bill_item_rows:
                computed = float(total_price or 0)
                if computed <= 0:
                    computed = float((qty or 0) * (unit_price or 0))
                per_bill_totals[bill_id] = per_bill_totals.get(bill_id, 0.0) + computed

        by_year: Dict[str, Dict[str, Any]] = {}
        for b in bills:
            if b.bill_date:
                s = str(b.bill_date)
                if "-" in s and len(s) >= 4:
                    year_key = s[:4]
                elif "/" in s:
                    parts = s.split("/")
                    year_key = parts[-1] if parts else s
                else:
                    year_key = s[:4]
            else:
                year_key = str(b.created_at.year) if b.created_at else "unknown"

            bill_total = float(b.total_amount or 0)
            if bill_total <= 0:
                bill_total = per_bill_totals.get(b.id, 0.0)

            bucket = by_year.setdefault(
                year_key, {"year": year_key, "total_spend": 0.0, "bill_count": 0}
            )
            bucket["total_spend"] += bill_total
            bucket["bill_count"] += 1

        years = sorted(by_year.values(), key=lambda x: x["year"])
        return {"device_id": device_id, "by_year": years}
    finally:
        db.close()

