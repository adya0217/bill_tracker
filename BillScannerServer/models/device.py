"""Device model for user authentication via device registration."""

from sqlalchemy import Column, String, TIMESTAMP, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Device(Base):
    """Registered mobile device — used as the user identity."""
    __tablename__ = "devices"

   
    device_id = Column(String(64), primary_key=True, index=True)

    device_name  = Column(String(255), nullable=True)
    device_model = Column(String(255), nullable=True)
    os_type      = Column(String(50),  nullable=True)   # iOS, Android
    os_version   = Column(String(50),  nullable=True)
    app_version  = Column(String(50),  nullable=True)
    fcm_token    = Column(String(500), nullable=True)   # push notification token

    registration_date = Column(TIMESTAMP, server_default=func.now())
    last_active       = Column(TIMESTAMP, server_default=func.now())

    user_notes = Column(Text, nullable=True)

   
    # String flags are error-prone ('y', 'YES', 1, True all appear in practice).
    # Boolean maps to a native BOOLEAN column in PostgreSQL.
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Relationship
    bills = relationship("Bill", back_populates="device")

    def __repr__(self) -> str:
        return f"<Device device_id='{self.device_id}' active={self.is_active}>"
