"""Vendor/Shop model for bill tracking."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, TIMESTAMP, Text, Numeric, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Vendor(Base):
    """Vendor / shop information extracted from or matched against bills."""
    __tablename__ = "vendors"

    id          = Column(Integer, primary_key=True, index=True)
    vendor_name = Column(String(255), nullable=False, index=True)
    mobile_no   = Column(String(20),  nullable=True)
    vendor_age  = Column(Integer,     nullable=True)
    vendor_address = Column(Text,     nullable=True)

    gst_number    = Column(String(15), nullable=True)   # store NULL when unknown

    branch_number = Column(String(50),  nullable=True)
    shop_type     = Column(String(100), nullable=True)

    # ── Contact
    email   = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)

    # ── Location
    city     = Column(String(100), nullable=True)
    state    = Column(String(100), nullable=True)
    pin_code = Column(String(10),  nullable=True)

    # ── Stats
    average_rating       = Column(Numeric(3, 2), nullable=True)
    total_bills_recorded = Column(Integer, default=0)

    # ── Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default = func.now(),
        onupdate       = datetime.utcnow,   # Python callable, not func.now()
    )

    vendor_notes = Column(Text, nullable=True)

    # ── Relationship
    bills = relationship("Bill", back_populates="vendor")

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name='{self.vendor_name}' gst='{self.gst_number}'>"


# Partial unique index: enforce GST number uniqueness ONLY for non-NULL,
# non-empty values.  This allows any number of vendors with gst_number=NULL.
gst_unique_index = Index(
    "uq_vendor_gst_number_nonempty",
    Vendor.gst_number,
    unique      = True,
    postgresql_where = Vendor.gst_number.isnot(None),
)
