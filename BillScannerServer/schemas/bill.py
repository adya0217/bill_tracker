"""Bill schemas."""

from pydantic import BaseModel, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from schemas.bill_item import BillItemResponse
from schemas.vendor import VendorResponse
from schemas.payment import PaymentDetailResponse


class BillCreate(BaseModel):
    """Schema for creating a bill (used by the bills router internally)."""
    device_id: str
    
    # The upload endpoint tries to resolve a vendor but must not crash if it can't.
    vendor_id: Optional[int] = None
    bill_number: Optional[str] = None
    bill_date:   Optional[str] = None
    bill_time:   Optional[str] = None
    generated_at: Optional[datetime] = None
    bill_year: Optional[int] = None
    bill_month: Optional[int] = None
    bill_day: Optional[int] = None
    subtotal:       Optional[Decimal] = None
    total_cgst:     Optional[Decimal] = None
    total_sgst:     Optional[Decimal] = None
    total_tax:      Optional[Decimal] = None
    total_discount: Decimal = Decimal(0)
    total_amount:   Decimal               # only hard required field
    points_added:    int = 0
    points_redeemed: int = 0
    loyalty_program: Optional[str] = None
    bill_status:     str = "stored"
    shop_type:       Optional[str] = None
    bill_category:   Optional[str] = None
    user_notes:      Optional[str] = None
    receipt_url:     Optional[str] = None


class BillResponse(BaseModel):
  
    id:          int
    device_id:   str
    
    vendor_id:   Optional[int] = None

    # ── Flat fields the frontend reads directly (populated by the router
    #    from the joined Vendor row — not stored as columns on bills table)
    merchant: Optional[str] = ""
    area:     Optional[str] = None

    bill_number: Optional[str] = None
    bill_date:   Optional[str] = None
    bill_time:   Optional[str] = None
    generated_at: Optional[datetime] = None
    bill_year: Optional[int] = None
    bill_month: Optional[int] = None
    bill_day: Optional[int] = None

    subtotal:       Optional[Decimal] = None
    total_cgst:     Optional[Decimal] = None
    total_sgst:     Optional[Decimal] = None
    
    # (what main.py serialises and what the frontend reads).
    total_tax:    Optional[Decimal] = None
    tax:          Optional[Decimal] = None   # alias — set equal to total_tax by router

    total_discount:  Decimal = Decimal(0)
    total_amount:    Decimal
    points_added:    int = 0
    points_redeemed: int = 0
    loyalty_program: Optional[str] = None
    bill_status:     str = "stored"
    shop_type:       Optional[str] = None
    bill_category:   Optional[str] = None
    ocr_confidence:  Optional[Decimal] = None
    pipeline:        Optional[str] = None   # "llm" | "heuristic" — debug field

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _sync_tax_alias(self) -> "BillResponse":
        
        if self.tax is None and self.total_tax is not None:
            self.tax = self.total_tax
        elif self.total_tax is None and self.tax is not None:
            self.total_tax = self.tax
        return self

    model_config = {"from_attributes": True, "populate_by_name": True}


class BillDetailedResponse(BillResponse):
    
    vendor:  Optional[VendorResponse]       = None
    items:   List[BillItemResponse]         = []
    payment: Optional[PaymentDetailResponse]= None
