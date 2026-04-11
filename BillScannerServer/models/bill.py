"""Bill model — master receipt record."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, TIMESTAMP, JSON, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Bill(Base):
    """Master bill record with complete transaction details."""
    __tablename__ = "bills"
    __table_args__ = (
        Index("ix_bills_device_generated_at", "device_id", "generated_at"),
        Index("ix_bills_device_year_month", "device_id", "bill_year", "bill_month"),
        Index("ix_bills_device_year_month_day", "device_id", "bill_year", "bill_month", "bill_day"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # ── Foreign keys
    device_id = Column(
        String(64), ForeignKey("devices.device_id"),
        index=True, nullable=False,
    )
    vendor_id = Column(
        Integer, ForeignKey("vendors.id"),
        
        nullable=True, index=True,
    )

    # ── Bill identification
    bill_number = Column(String(100), nullable=True)   # from OCR
    bill_date   = Column(String(20),  nullable=True)   # YYYY-MM-DD string
    bill_time   = Column(String(20),  nullable=True)
    generated_at = Column(TIMESTAMP, nullable=True, index=True)
    bill_year = Column(Integer, nullable=True, index=True)
    bill_month = Column(Integer, nullable=True, index=True)
    bill_day = Column(Integer, nullable=True, index=True)

    # ── Amounts & taxes
    subtotal        = Column(Numeric(12, 2), nullable=True)
    total_cgst      = Column(Numeric(10, 2), nullable=True)
    total_sgst      = Column(Numeric(10, 2), nullable=True)
    total_tax       = Column(Numeric(12, 2), nullable=True)   # all taxes combined
    total_discount  = Column(Numeric(10, 2), default=0)
    total_amount    = Column(Numeric(12, 2), nullable=False) 

    # ── Loyalty program
    points_added    = Column(Integer, default=0)
    points_redeemed = Column(Integer, default=0)
    loyalty_program = Column(String(100), nullable=True)

    # ── Bill status & categorisation
    bill_status   = Column(String(50),  default="stored")
    shop_type     = Column(String(100), nullable=True)
    bill_category = Column(String(100), nullable=True)

    # ── OCR & processing
    raw_ocr         = Column(JSON, nullable=True)
    raw_llm         = Column(JSON, nullable=True)
    ocr_confidence  = Column(Numeric(5, 2), nullable=True)

    # ── Notes & images
    user_notes      = Column(Text,         nullable=True)
    receipt_images  = Column(JSON,         nullable=True)
    receipt_url     = Column(String(500),  nullable=True)

    # ── Timestamps
    created_at       = Column(TIMESTAMP, server_default=func.now())
    bill_scanned_date= Column(TIMESTAMP, server_default=func.now())

 
    updated_at = Column(
        TIMESTAMP,
        server_default = func.now(),
        onupdate       = datetime.utcnow,   # ← Python callable, not SQL expression
    )

    # ── Relationships
    vendor  = relationship("Vendor",        back_populates="bills")
    device  = relationship("Device",        back_populates="bills")
    items   = relationship("BillItem",      back_populates="bill",
                           cascade="all, delete-orphan")
    payment = relationship("PaymentDetail", back_populates="bill",
                           uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (f"<Bill id={self.id} device='{self.device_id}' "
                f"vendor_id={self.vendor_id} total={self.total_amount}>")
