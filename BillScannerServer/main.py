from config import cors_origins_list, get_settings
from typing import Any, Dict

settings = get_settings()

import logging
import os
import traceback

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from middleware.api_request_logging import api_request_logging_middleware
from sqlalchemy import text

# ── DB setup
from database import engine, Base, SessionLocal

from models import Bill, BillItem, Category, Device, Vendor, PaymentDetail, ApiRequestLog

# ── API routers
from api.auth      import router as auth_router
from api.vendors   import router as vendors_router
from api.bills     import router as bills_router
from api.analytics import router as analytics_router

# ── Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("main")
API_PREFIX = "/api/v1"


def _ensure_master_bill_columns() -> None:
    
    statements = [
        "ALTER TABLE bills ADD COLUMN IF NOT EXISTS generated_at TIMESTAMP",
        "ALTER TABLE bills ADD COLUMN IF NOT EXISTS bill_year INTEGER",
        "ALTER TABLE bills ADD COLUMN IF NOT EXISTS bill_month INTEGER",
        "ALTER TABLE bills ADD COLUMN IF NOT EXISTS bill_day INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_bills_device_generated_at ON bills (device_id, generated_at)",
        "CREATE INDEX IF NOT EXISTS ix_bills_device_year_month ON bills (device_id, bill_year, bill_month)",
        "CREATE INDEX IF NOT EXISTS ix_bills_device_year_month_day ON bills (device_id, bill_year, bill_month, bill_day)",
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

# ──────────────────────────────────────────────
# DB INIT
# ──────────────────────────────────────────────

log.info("Creating / verifying database tables …")
Base.metadata.create_all(bind=engine)
_ensure_master_bill_columns()
log.info("Database tables ready")

# ── Seed a default vendor so /bills/upload/ works out of the box
_session = SessionLocal()
try:
    if not _session.query(Vendor).filter_by(id=1).first():
        log.info("Seeding default vendor #1 …")
        _session.add(Vendor(
            vendor_name    = "Default Store",
            gst_number     = "",
            shop_type      = "General",
            city           = "",
            vendor_address = "",
        ))
        _session.commit()
        log.info("Default vendor created")
    else:
        log.info("Default vendor already exists")
finally:
    _session.close()

# ── Seed default categories
_DEFAULT_CATEGORIES = [
    "Groceries", "Household", "Medical", "Electronics",
    "Dining", "Beverages", "Snacks", "Other",
]
_session = SessionLocal()
try:
    existing = {c.name for c in _session.query(Category).all()}
    new_cats = [Category(name=n) for n in _DEFAULT_CATEGORIES if n not in existing]
    if new_cats:
        _session.add_all(new_cats)
        _session.commit()
        log.info(f" Seeded {len(new_cats)} new categories")
    else:
        log.info("All categories already exist")
finally:
    _session.close()

# ──────────────────────────────────────────────
# APP
# ──────────────────────────────────────────────

app = FastAPI(
    title       = "Bill Tracker API",
    description = "Comprehensive bill tracking system with OCR and analytics",
    version     = "2.0.0",
)

# ── CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins     = cors_origins_list(),
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── Every REST request → row in `api_request_logs`; failures include response body + traceback when applicable
@app.middleware("http")
async def _log_requests_to_db(request: Request, call_next):
    return await api_request_logging_middleware(request, call_next)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Capture server-side trace for unhandled errors — middleware persists it on the request log row."""
    tb = traceback.format_exc()
    request.state.server_traceback = tb
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# ── Uploads directory
os.makedirs(settings.upload_folder, exist_ok=True)

# ── Routers
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(vendors_router, prefix=API_PREFIX)
app.include_router(bills_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)


# ──────────────────────────────────────────────
# HEALTH & INFO
# ──────────────────────────────────────────────

@app.get("/", tags=["health"])
def health_check() -> Dict[str, Any]:
    return {"status": "healthy", "service": "Bill Tracker API", "version": "2.0.0"}


@app.get("/api-info", tags=["health"])
def api_info() -> Dict[str, Any]:
    return {
        "service": "Bill Tracker API",
        "version": "2.0.0",
        "endpoints": {
            "auth": {
                "register_device": f"POST {API_PREFIX}/auth/register-device",
                "validate_device": f"POST {API_PREFIX}/auth/validate-device/{{device_id}}",
                "get_device":      f"GET  {API_PREFIX}/auth/device/{{device_id}}",
            },
            "vendors": {
                "create": f"POST {API_PREFIX}/vendors/",
                "get":    f"GET  {API_PREFIX}/vendors/{{vendor_id}}",
                "list":   f"GET  {API_PREFIX}/vendors/",
                "update": f"PUT  {API_PREFIX}/vendors/{{vendor_id}}",
                "delete": f"DELETE {API_PREFIX}/vendors/{{vendor_id}}",
            },
            "bills": {
                "upload":     f"POST {API_PREFIX}/bills/upload/",
                "get":        f"GET  {API_PREFIX}/bills/{{bill_id}}",
                "list":       f"GET  {API_PREFIX}/bills/device/{{device_id}}",
                "update":     f"PUT  {API_PREFIX}/bills/{{bill_id}}",
                "delete":     f"DELETE {API_PREFIX}/bills/{{bill_id}}",
            },
            "analytics": f"GET {API_PREFIX}/analytics/summary/{{device_id}}",
        },
    }


# ──────────────────────────────────────────────
# LEGACY ENDPOINTS  (kept for backwards compat)
# ──────────────────────────────────────────────

@app.post("/upload-bill/", tags=["legacy"], deprecated=True)
async def upload_bill_legacy():
    
    raise HTTPException(
        status_code = status.HTTP_410_GONE,
        detail      = "Deprecated. Use POST /bills/upload/",
    )


@app.get("/bills/", tags=["legacy"])
def list_bills_legacy(
    device_id: str,
    page:      int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    
    db = SessionLocal()
    try:
        query = (
            db.query(Bill, Vendor)
            .outerjoin(Vendor, Bill.vendor_id == Vendor.id)   # outerjoin – vendor may be null
            .filter(Bill.device_id == device_id)
            .order_by(Bill.created_at.desc())
        )

        total     = query.count()
        page      = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        rows      = query.offset((page - 1) * page_size).limit(page_size).all()

        log.debug(f"[list_bills_legacy] device={device_id}  page={page}  "
                  f"total={total}  returned={len(rows)}")

        items = [
            {
                "id":           b.id,
                "merchant":     v.vendor_name if v else "",
                "area":         v.city if v else None,
                "bill_date":    b.bill_date,
                "bill_number":  b.bill_number,
                "total_amount": float(b.total_amount or 0),
                "created_at":   str(b.created_at) if b.created_at else None,
            }
            for b, v in rows
        ]

        return {"items": items, "page": page, "page_size": page_size, "total": total}

    except Exception as exc:
        log.exception(f"[list_bills_legacy] DB error: {exc}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        db.close()


@app.get("/bill/{bill_id}", tags=["legacy"])
def get_bill_details_legacy(bill_id: int) -> Dict[str, Any]:
   
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            log.warning(f"[get_bill_details] bill_id={bill_id} not found")
            return JSONResponse(status_code=404, content={"error": "Bill not found"})

        log.debug(f"[get_bill_details] bill_id={bill_id}  vendor_id={bill.vendor_id}")

        # ── line items with category name
        raw_items = (
            db.query(BillItem, Category)
            .outerjoin(Category, BillItem.category_id == Category.id)
            .filter(BillItem.bill_id == bill_id)
            .all()
        )

        log.debug(f"[get_bill_details] {len(raw_items)} line items")

        serialized_items = []
        for bi, cat in raw_items:
            cat_name = cat.name if cat else "Other"
            serialized_items.append({
                # expose BOTH field names so frontend/other clients work regardless
                "name":         bi.product_name or "",
                "product_name": bi.product_name or "",
                "sku":          bi.sku          or "",
                "quantity":     float(bi.quantity    or 1),
                "unit_price":   float(bi.unit_price  or 0),
                "total_price":  float(bi.total_price or 0),
                "tax":          float(bi.tax         or 0),
                "category":     cat_name,
            })

        vendor = db.query(Vendor).filter(Vendor.id == bill.vendor_id).first() if bill.vendor_id else None

        response = {
            "id":           bill.id,
            "device_id":    bill.device_id,
            "merchant":     vendor.vendor_name if vendor else "",
            "area":         vendor.city if vendor else None,
            "bill_date":    bill.bill_date,
            "bill_number":  bill.bill_number,
            "subtotal":     float(bill.subtotal    or 0),
            "tax":          float(bill.total_tax   or 0),  
            "total_amount": float(bill.total_amount or 0),
            "created_at":   str(bill.created_at) if bill.created_at else None,
            "items":        serialized_items,
            "vendor": {
                "id":          vendor.id          if vendor else None,
                "vendor_name": vendor.vendor_name if vendor else None,
            },
        }

        log.debug(f"[get_bill_details] response keys={list(response.keys())}")
        return response

    except Exception as exc:
        log.exception(f"[get_bill_details] error for bill_id={bill_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host    = settings.uvicorn_host,
        port    = settings.uvicorn_port,
        reload  = True,          # auto-reload on code changes during dev
        log_level = settings.log_level.lower(),
    )
