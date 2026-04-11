"""Payment detail schemas."""

from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class PaymentDetailCreate(BaseModel):
    bill_id:          int
    payment_method:   str          # cash, card, upi, wallet
    card_type:        Optional[str]     = None
    card_last_4:      Optional[str]     = None
    card_network:     Optional[str]     = None
    upi_id:           Optional[str]     = None
    transaction_id:   Optional[str]     = None
    amount_paid:      Decimal
    change_amount:    Optional[Decimal] = None
    payment_status:   str               = "completed"
    reference_number: Optional[str]     = None
    notes:            Optional[str]     = None


class PaymentDetailResponse(BaseModel):
    id:               int
    bill_id:          int
    payment_method:   str
    card_last_4:      Optional[str]     = None
    card_network:     Optional[str]     = None
    transaction_id:   Optional[str]     = None
    amount_paid:      Decimal
    change_amount:    Optional[Decimal] = None
    payment_status:   str

    model_config = {"from_attributes": True}
