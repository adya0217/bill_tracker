"""Bill line-items model with full GST breakdown."""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, TIMESTAMP, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class BillItem(Base):
    """Individual line items on a bill."""
    __tablename__ = "bill_items"

    id      = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)

  
    product_name = Column(String(255), nullable=True)
    product_code = Column(String(100), nullable=True)
    sku          = Column(String(100), nullable=True)
    category_id  = Column(Integer, ForeignKey("categories.id"), nullable=True)

   
    quantity   = Column(Numeric(10, 3), nullable=True)   # fractional OK (1.5 kg)
    unit       = Column(String(50),     nullable=True)   # kg, litre, piece …
    unit_price = Column(Numeric(10, 2), nullable=True)
    subtotal   = Column(Numeric(12, 2), nullable=True)   # qty × unit_price — COMPUTED by router

    # ── GST breakdown (nullable — not all receipts have GST detail)
    cgst_rate   = Column(Numeric(5, 2),  nullable=True)
    sgst_rate   = Column(Numeric(5, 2),  nullable=True)
    igst_rate   = Column(Numeric(5, 2),  nullable=True)
    cgst_amount = Column(Numeric(10, 2), nullable=True)
    sgst_amount = Column(Numeric(10, 2), nullable=True)
    igst_amount = Column(Numeric(10, 2), nullable=True)
    total_tax   = Column(Numeric(12, 2), nullable=True)

    # ── Final price
    total_price = Column(Numeric(12, 2), nullable=True)  # subtotal + total_tax

    # ── Discounts
    item_discount        = Column(Numeric(10, 2), default=0)
    discount_percentage  = Column(Numeric(5, 2),  nullable=True)

    # ── Additional details
    hsn_code   = Column(String(50),  nullable=True)
    item_notes = Column(String(500), nullable=True)
    item_data  = Column(JSON,        nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # ── Relationships
    bill     = relationship("Bill",     back_populates="items")
    category = relationship("Category", back_populates="bill_items")

    # ── Convenience alias
    # The LLM service and frontend both use `name`; the DB column is
    # `product_name`.  Expose both so serialisers work with either.
    @property
    def name(self) -> str:
        return self.product_name or ""

    def __repr__(self) -> str:
        return (f"<BillItem id={self.id} bill_id={self.bill_id} "
                f"name='{self.product_name}' total={self.total_price}>")
