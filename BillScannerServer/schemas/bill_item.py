"""Bill item schemas with GST details."""

from pydantic import BaseModel, model_validator
from typing import Optional
from decimal import Decimal


class BillItemCreate(BaseModel):
   
    bill_id:      int
    # FIX: product_name Optional — matches nullable=True on the model.
    # LLM can occasionally produce an empty/None name for garbled OCR lines.
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    sku:          Optional[str] = None
    category_id:  Optional[int] = None

    quantity:   Optional[Decimal] = None
    unit:       Optional[str]     = None
    unit_price: Optional[Decimal] = None

    # FIX: subtotal Optional — LLM/receipt_parser never produce this field.
    # The bills router computes it as quantity × unit_price before saving.
    subtotal: Optional[Decimal] = None

    cgst_rate:   Optional[Decimal] = None
    sgst_rate:   Optional[Decimal] = None
    igst_rate:   Optional[Decimal] = None
    cgst_amount: Optional[Decimal] = None
    sgst_amount: Optional[Decimal] = None
    igst_amount: Optional[Decimal] = None
    total_tax:   Optional[Decimal] = None

    # FIX: total_price Optional for same reason as subtotal
    total_price: Optional[Decimal] = None

    item_discount:       Decimal           = Decimal(0)
    discount_percentage: Optional[Decimal] = None
    hsn_code:            Optional[str]     = None
    item_notes:          Optional[str]     = None

    @model_validator(mode="after")
    def _compute_subtotal(self) -> "BillItemCreate":
        
        if self.subtotal is None and self.quantity and self.unit_price:
            self.subtotal = self.quantity * self.unit_price
        return self


class BillItemResponse(BaseModel):
  
    id:      int
    bill_id: int

    # FIX: expose `name` alias — frontend reads item.name, not item.product_name
    name:         Optional[str] = ""
    product_name: Optional[str] = ""

    product_code: Optional[str]     = None
    sku:          Optional[str]     = None

    quantity:   Optional[Decimal] = None
    unit:       Optional[str]     = None
    unit_price: Optional[Decimal] = None

    cgst_rate:   Optional[Decimal] = None
    sgst_rate:   Optional[Decimal] = None
    cgst_amount: Optional[Decimal] = None
    sgst_amount: Optional[Decimal] = None

    # FIX: add `tax` — frontend reads item.tax
    tax:         Optional[Decimal] = None
    total_price: Optional[Decimal] = None

    item_discount: Decimal = Decimal(0)

    # FIX: add `category` string — frontend reads item.category.
    # This is populated by the router from the joined Category.name.
    category: Optional[str] = "Other"

    @model_validator(mode="after")
    def _sync_name_alias(self) -> "BillItemResponse":
        
        if not self.name and self.product_name:
            self.name = self.product_name
        elif not self.product_name and self.name:
            self.product_name = self.name
        return self

    model_config = {"from_attributes": True, "populate_by_name": True}
