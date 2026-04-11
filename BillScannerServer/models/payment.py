"""Payment details model for bills."""

from sqlalchemy import Column, Integer, String, Numeric, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class PaymentDetail(Base):
    """Payment information for each bill."""
    __tablename__ = "payment_details"

    id      = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)

    payment_method = Column(String(50), nullable=False)  # cash, card, upi, wallet …

    # ── Card details
    card_type    = Column(String(50), nullable=True)   # credit, debit, prepaid
    card_last_4  = Column(String(4),  nullable=True)
    card_network = Column(String(50), nullable=True)   # VISA, MasterCard, RuPay

    # ── UPI / digital payment
    upi_id         = Column(String(255), nullable=True)
    transaction_id = Column(String(100), nullable=True, index=True)

    # ── Cash details
    amount_paid   = Column(Numeric(10, 2), nullable=False)
    change_amount = Column(Numeric(10, 2), nullable=True)

    # ── Status
    payment_status   = Column(String(50), default="completed")
    reference_number = Column(String(100), nullable=True)
    notes            = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # ── Relationship
    bill = relationship("Bill", back_populates="payment")

    def __repr__(self) -> str:
        return (f"<PaymentDetail id={self.id} bill_id={self.bill_id} "
                f"method='{self.payment_method}' amount={self.amount_paid}>")
