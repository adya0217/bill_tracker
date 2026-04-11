"""Device registration schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceRegisterRequest(BaseModel):
    """Schema for device registration."""
    device_name:  str
    device_model: Optional[str] = None
    os_type:      str            # "iOS" | "Android"
    os_version:   Optional[str] = None
    app_version:  Optional[str] = None
    fcm_token:    Optional[str] = None
    user_notes:   Optional[str] = None


class DeviceResponse(BaseModel):
    """Device info response."""
    device_id:    str
    device_name:  Optional[str] = None
    device_model: Optional[str] = None
    os_type:      Optional[str] = None
    os_version:   Optional[str] = None
    registration_date: Optional[datetime] = None
    last_active:       Optional[datetime] = None
  
    # Pydantic will coerce a DB True/False to Python bool correctly.
    is_active: bool = True

    model_config = {"from_attributes": True}
