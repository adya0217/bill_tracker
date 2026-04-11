"""Vendor/Shop management endpoints."""
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from database import SessionLocal
from models.vendor import Vendor
from schemas.vendor import VendorCreate, VendorResponse

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.post("/", response_model=VendorResponse)
async def create_vendor(vendor: VendorCreate) -> VendorResponse:
    """Create a new vendor/shop record."""
    db = SessionLocal()
    try:
        # Check if vendor already exists by name and GST number
        existing = db.query(Vendor).filter(
            (Vendor.vendor_name == vendor.vendor_name) &
            (Vendor.gst_number == vendor.gst_number if vendor.gst_number else True)
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vendor already exists"
            )
        
        new_vendor = Vendor(**vendor.dict())
        db.add(new_vendor)
        db.commit()
        db.refresh(new_vendor)
        
        return VendorResponse.from_orm(new_vendor)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    finally:
        db.close()


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(vendor_id: int) -> VendorResponse:
    """Get vendor details by ID."""
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )
        return VendorResponse.from_orm(vendor)
    finally:
        db.close()


@router.get("/", response_model=List[VendorResponse])
async def list_vendors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shop_type: str = Query(None),
    city: str = Query(None)
) -> List[VendorResponse]:
    """List vendors with optional filtering."""
    db = SessionLocal()
    try:
        query = db.query(Vendor)
        
        if shop_type:
            query = query.filter_by(shop_type=shop_type)
        if city:
            query = query.filter_by(city=city)
        
        vendors = query.offset(skip).limit(limit).all()
        return [VendorResponse.from_orm(v) for v in vendors]
        
    finally:
        db.close()


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(vendor_id: int, vendor_data: VendorCreate) -> VendorResponse:
    """Update vendor information."""
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )
        
        update_data = vendor_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(vendor, field, value)
        
        db.commit()
        db.refresh(vendor)
        
        return VendorResponse.from_orm(vendor)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/{vendor_id}")
async def delete_vendor(vendor_id: int) -> Dict[str, str]:
    """Delete a vendor record."""
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )
        
        db.delete(vendor)
        db.commit()
        
        return {"message": "Vendor deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
