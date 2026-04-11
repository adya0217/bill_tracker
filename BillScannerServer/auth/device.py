"""Device registration and unique ID generation."""
import uuid
import hashlib
from datetime import datetime
from typing import Tuple


def generate_device_id() -> Tuple[str, str]:
    """
    Generate unique device ID in hex format.
    
    Returns:
        Tuple[str, str]: (hex_id, octal_id) for flexibility
    
    Example:
        hex_id: "a3f5c8e2b1d94f7c"
        octal_id: "51764316650765174370"
    """
    # Create a unique identifier combining UUID and timestamp
    unique_str = f"{uuid.uuid4().hex}{datetime.now().timestamp()}"
    
    # Hash it for additional uniqueness
    hash_obj = hashlib.sha256(unique_str.encode())
    hash_bytes = hash_obj.digest()[:8]  # Take first 8 bytes
    
    # Convert to int then to hex and octal
    unique_int = int.from_bytes(hash_bytes, byteorder='big')
    
    hex_id = hex(unique_int)[2:]  # Remove '0x' prefix
    octal_id = oct(unique_int)[2:]  # Remove '0o' prefix
    
    return hex_id, octal_id


def validate_device_id_format(device_id: str) -> bool:
    """
    Validate if device_id is in valid hex or octal format.
    
    Args:
        device_id: Device ID to validate
        
    Returns:
        bool: True if valid format
    """
    if not device_id or len(device_id) < 8:
        return False
    
    try:
        # Try hex
        int(device_id, 16)
        return True
    except ValueError:
        pass
    
    try:
        # Try octal
        int(device_id, 8)
        return True
    except ValueError:
        pass
    
    return False
