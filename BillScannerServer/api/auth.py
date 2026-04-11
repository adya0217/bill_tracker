"""Device registration and authentication endpoints."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from database import SessionLocal
from models.device import Device
from schemas.device import DeviceRegisterRequest, DeviceResponse
from auth.device import generate_device_id, validate_device_id_format

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register-device", response_model=DeviceResponse)
async def register_device(request: DeviceRegisterRequest) -> Dict[str, Any]:
    """
    Register a new device for bill tracking.
    
    Generates a unique hex-based device ID automatically.
    Returns device_id that should be stored on client permanently.
    
    Args:
        request: Device registration details
        
    Returns:
        Device registration response with unique device_id
    """
    db = SessionLocal()
    try:
        # Generate unique hex device ID
        hex_id, octal_id = generate_device_id()
        
        # Check if device ID already exists (very unlikely but safe)
        existing = db.query(Device).filter_by(device_id=hex_id).first()
        if existing:
            # Regenerate if collision
            hex_id, octal_id = generate_device_id()
        
        # Create device record
        device = Device(
            device_id=hex_id,
            device_name=request.device_name,
            device_model=request.device_model,
            os_type=request.os_type,
            os_version=request.os_version,
            app_version=request.app_version,
            fcm_token=request.fcm_token,
            user_notes=request.user_notes,
            is_active=True
        )
        
        db.add(device)
        db.commit()
        db.refresh(device)
        
        print(f"[auth] Device registered: {hex_id} | Octal: {octal_id}")
        
        return DeviceResponse.from_orm(device)
        
    except Exception as e:
        db.rollback()
        print(f"[auth] Device registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )
    finally:
        db.close()


@router.post("/validate-device/{device_id}")
async def validate_device(device_id: str) -> Dict[str, Any]:
    """
    Validate if a device ID is registered and active.
    
    Args:
        device_id: Device ID to validate
        
    Returns:
        Validation result with device status
    """
    db = SessionLocal()
    try:
        # Check format
        if not validate_device_id_format(device_id):
            return {
                "valid": False,
                "registered": False,
                "message": "Invalid device ID format"
            }
        
        # Check if registered
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            return {
                "valid": True,
                "registered": False,
                "message": "Device not registered"
            }
        
        if not device.is_active:
            return {
                "valid": True,
                "registered": True,
                "active": False,
                "message": "Device is inactive"
            }
        
        return {
            "valid": True,
            "registered": True,
            "active": True,
            "device_name": device.device_name,
            "last_active": device.last_active
        }
        
    finally:
        db.close()


@router.get("/device/{device_id}", response_model=DeviceResponse)
async def get_device_info(device_id: str) -> DeviceResponse:
    """Get registered device information."""
    db = SessionLocal()
    try:
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        return DeviceResponse.from_orm(device)
    finally:
        db.close()
