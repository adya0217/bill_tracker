"""Vendor/Shop schemas."""

from pydantic import BaseModel
from typing import Optional


class VendorCreate(BaseModel):
    vendor_name:    str
    mobile_no:      Optional[str] = None
    vendor_age:     Optional[int] = None
    vendor_address: Optional[str] = None
    # Store None when no GST number — never store "" (causes unique constraint crash)
    gst_number:     Optional[str] = None
    branch_number:  Optional[str] = None
    shop_type:      Optional[str] = None
    email:          Optional[str] = None
    website:        Optional[str] = None
    city:           Optional[str] = None
    state:          Optional[str] = None
    pin_code:       Optional[str] = None
    vendor_notes:   Optional[str] = None


class VendorResponse(BaseModel):
    id:                   int
    vendor_name:          str
    mobile_no:            Optional[str]   = None
    vendor_age:           Optional[int]   = None
    vendor_address:       Optional[str]   = None
    gst_number:           Optional[str]   = None
    branch_number:        Optional[str]   = None
    shop_type:            Optional[str]   = None
    city:                 Optional[str]   = None
    state:                Optional[str]   = None
    pin_code:             Optional[str]   = None
    average_rating:       Optional[float] = None
    total_bills_recorded: int             = 0

    model_config = {"from_attributes": True}
