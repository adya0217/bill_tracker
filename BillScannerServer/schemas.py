

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, field_validator


# ──────────────────────────────────────────────
# ITEM
# ──────────────────────────────────────────────

class ItemSchema(BaseModel):
    
    
    name:         str     = ""
    product_name: str     = ""   
    sku:          Optional[str] = ""
    quantity:     float   = 1.0
    unit_price:   float   = 0.0
    total_price:  float   = 0.0
    tax:          float   = 0.0
    category:     str     = "Other"

    @field_validator("name", mode="before")
    @classmethod
    def _fill_name(cls, v: object) -> str:
        return str(v).strip() if v else ""

    @field_validator("product_name", mode="before")
    @classmethod
    def _fill_product_name(cls, v: object) -> str:
        return str(v).strip() if v else ""

    model_config = {"populate_by_name": True}


# ──────────────────────────────────────────────
# BILL  (response)
# ──────────────────────────────────────────────

class BillSchema(BaseModel):
   
    id:           Optional[int]  = None
    merchant:     str            = ""
    area:         Optional[str]  = ""
    bill_date:    Optional[str]  = ""   # YYYY-MM-DD
    bill_number:  Optional[str]  = ""   # invoice / receipt number
    subtotal:     float          = 0.0
    tax:          float          = 0.0 
    total_amount: float          = 0.0
    items:        List[ItemSchema] = []
    pipeline:     Optional[str]  = None  # "llm" | "heuristic" 

    model_config = {"populate_by_name": True}


# ──────────────────────────────────────────────
# BILL LIST ITEM  (summary row in bills list)
# ──────────────────────────────────────────────

class BillListItemSchema(BaseModel):
    
    id:           int
    merchant:     str            = ""
    area:         Optional[str]  = None
    bill_date:    Optional[str]  = None
    total_amount: float          = 0.0
    created_at:   Optional[str]  = None

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# PAGINATED RESPONSE
# ──────────────────────────────────────────────

class PaginatedBillsSchema(BaseModel):
    items:     List[BillListItemSchema]
    page:      int
    page_size: int
    total:     int


# ──────────────────────────────────────────────
# UPLOAD REQUEST  (form fields validated here)
# ──────────────────────────────────────────────

class BillUploadMeta(BaseModel):
    
    device_id:      str
    vendor_id:      Optional[int]   = 1
    payment_method: Optional[str]   = "cash"
    amount_paid:    Optional[float] = 0.0
    points_added:   Optional[int]   = 0
