
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, TIMESTAMP, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


# ──────────────────────────────────────────────
# VENDOR
# ──────────────────────────────────────────────

class Vendor(Base):
    __tablename__ = "vendors"

    id             = Column(Integer, primary_key=True, index=True)
    vendor_name    = Column(String(255), nullable=False)
    gst_number     = Column(String(20),  nullable=True)
    shop_type      = Column(String(100), nullable=True)
    city           = Column(String(100), nullable=True)
    vendor_address = Column(Text,        nullable=True)
    created_at     = Column(TIMESTAMP,   server_default=func.now())

    bills = relationship("Bill", back_populates="vendor")

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name='{self.vendor_name}'>"


# ──────────────────────────────────────────────
# DEVICE 
# ──────────────────────────────────────────────

class Device(Base):
    __tablename__ = "devices"

    id         = Column(Integer,   primary_key=True, index=True)
    device_id  = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    bills = relationship("Bill", back_populates="device")

    def __repr__(self) -> str:
        return f"<Device id={self.id} device_id='{self.device_id}'>"


# ──────────────────────────────────────────────
# CATEGORY
# ──────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    bill_items = relationship("BillItem", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name='{self.name}'>"


# ──────────────────────────────────────────────
# BILL
# ──────────────────────────────────────────────

class Bill(Base):
    """
    One scanned receipt.

    Relationships:
        vendor    the store where the purchase was made
        device    the mobile device that uploaded the bill
        items     line items parsed from the receipt
        payment   payment details
    """
    __tablename__ = "bills"

    id          = Column(Integer, primary_key=True, index=True)

    # ── foreign keys
    device_id   = Column(String(255), ForeignKey("devices.device_id"), nullable=False, index=True)
    vendor_id   = Column(Integer,     ForeignKey("vendors.id"),        nullable=True)

    # ── receipt metadata
    bill_number = Column(String(100), nullable=True)   # invoice / receipt number from OCR
    bill_date   = Column(String(50),  nullable=True)   # YYYY-MM-DD string from OCR

    # ── amounts
    subtotal    = Column(Numeric(12, 2), nullable=True, default=0)
    total_tax   = Column(Numeric(12, 2), nullable=True, default=0)   
    total_amount= Column(Numeric(12, 2), nullable=False, default=0)

    # ── raw data for debugging
    raw_ocr     = Column(JSON, nullable=True)   # list of OCR lines
    raw_llm     = Column(JSON, nullable=True)   # raw LLM response dict

    created_at  = Column(TIMESTAMP, server_default=func.now())

    # ── relationships
    vendor  = relationship("Vendor",        back_populates="bills")
    device  = relationship("Device",        back_populates="bills")
    items   = relationship("BillItem",      back_populates="bill", cascade="all, delete-orphan")
    payment = relationship("PaymentDetail", back_populates="bill",  uselist=False,
                           cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (f"<Bill id={self.id} device='{self.device_id}' "
                f"vendor_id={self.vendor_id} total={self.total_amount}>")


# ──────────────────────────────────────────────
# BILL ITEM
# ──────────────────────────────────────────────

class BillItem(Base):
    
    __tablename__ = "bill_items"

    id           = Column(Integer, primary_key=True, index=True)
    bill_id      = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("categories.id"), nullable=True)

    product_name = Column(String(500), nullable=True)   # primary column name
    sku          = Column(String(100), nullable=True)
    quantity     = Column(Numeric(10, 3), nullable=True, default=1)
    unit_price   = Column(Numeric(12, 2), nullable=True, default=0)
    total_price  = Column(Numeric(12, 2), nullable=True, default=0)
    tax          = Column(Numeric(12, 2), nullable=True, default=0)

  
    bill     = relationship("Bill",     back_populates="items")
    category = relationship("Category", back_populates="bill_items")

   
    @property
    def name(self) -> str:
        return self.product_name or ""

    def __repr__(self) -> str:
        return (f"<BillItem id={self.id} bill_id={self.bill_id} "
                f"name='{self.product_name}' total={self.total_price}>")


# ──────────────────────────────────────────────
# PAYMENT DETAIL
# ──────────────────────────────────────────────

class PaymentDetail(Base):
    __tablename__ = "payment_details"

    id             = Column(Integer, primary_key=True, index=True)
    bill_id        = Column(Integer, ForeignKey("bills.id"), nullable=False, unique=True)
    vendor_id      = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    payment_method = Column(String(50),  nullable=True)
    amount_paid    = Column(Numeric(12, 2), nullable=True, default=0)
    points_added   = Column(Integer,     nullable=True, default=0)
    created_at     = Column(TIMESTAMP,   server_default=func.now())

    bill = relationship("Bill", back_populates="payment")

    def __repr__(self) -> str:
        return f"<PaymentDetail id={self.id} bill_id={self.bill_id} method='{self.payment_method}'>"
