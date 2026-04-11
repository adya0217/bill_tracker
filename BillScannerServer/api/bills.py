"""Bill management endpoints for uploading and retrieving bills."""
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import shutil
import os
import uuid
from datetime import datetime

from config import get_settings
from database import SessionLocal
from models.bill import Bill
from models.bill_item import BillItem
from models.category import Category
from models.device import Device
from models.vendor import Vendor
from models.payment import PaymentDetail
from schemas.bill import BillCreate, BillResponse, BillDetailedResponse
from schemas.bill_item import BillItemCreate, BillItemResponse
from schemas.payment import PaymentDetailCreate, PaymentDetailResponse

from services.file_text_extractor import extract_bill_text_payload, SUPPORTED_EXTENSIONS
from services.receipt_parser import parse_receipt
from services.categorization import categorize_item
from auth.device import validate_device_id_format

router = APIRouter(prefix="/bills", tags=["bills"])

UPLOAD_FOLDER = get_settings().upload_folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert mixed OCR values to float safely."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_bill_datetime(structured: Dict[str, Any]) -> datetime:
    """
    Build bill datetime from parser fields.
    Falls back to current time if parser date/time is unavailable.
    """
    bill_date = (structured.get("bill_date") or "").strip()
    bill_time = (structured.get("bill_time") or "").strip()

    if bill_date and bill_time:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(f"{bill_date} {bill_time}", fmt)
            except ValueError:
                continue

    if bill_date:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(bill_date, fmt)
            except ValueError:
                continue

    return datetime.utcnow()


@router.post("/upload/")
async def upload_bill(
    background_tasks: BackgroundTasks,
    device_id: str = Form(...),
    vendor_id: int = Form(...),
    file: UploadFile = File(...),
    payment_method: str = Form(...),
    amount_paid: float = Form(...),
    points_added: int = Form(0),
    loyalty_program: str = Form(None)
) -> Dict[str, Any]:
    """
    Upload a bill receipt image.
    
    Process:
    1. Save image file
    2. Extract text via OCR
    3. Parse and structure bill data
    4. Store bill, items, and vendor info
    5. Record payment details
    
    Args:
        device_id: Customer device ID (hex format)
        vendor_id: Vendor/Shop ID
        file: Receipt image file
        payment_method: Payment method (cash, card, upi, etc.)
        amount_paid: Amount paid in this transaction
        points_added: Loyalty points earned
        loyalty_program: Loyalty program name if applicable
    """
    print(f"[upload] Bill upload request from device: {device_id}")
    print(f"[upload] Filename: {file.filename}")
    
    db = SessionLocal()
    try:
        if not validate_device_id_format(device_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid device_id format (must be valid hex/octal)",
            )

        # Validate device exists
        # Note: In production, would verify device is registered
        
        # Validate vendor exists
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )

        # Dev-friendly behavior: create the device row if it doesn't exist yet.
        # Your mobile app can upload before /auth/register-device is called.
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            db.add(Device(device_id=device_id))
            db.commit()
        
        # Save uploaded file
        _, ext = os.path.splitext(file.filename or "")
        if not ext:
            ext = ".jpg"
        ext = ext.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}",
            )

        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[upload] File saved: {file_path}")
        
        # Text extraction (OCR for images, parser for docs/spreadsheets/pdf)
        print("INFO: Extracting text lines...")
        ocr_payload = extract_bill_text_payload(file_path)
        ocr_lines = ocr_payload.get("lines", []) if isinstance(ocr_payload, dict) else []
        print(f"INFO: Extracted lines={len(ocr_lines)}")
        
        # Parse receipt structure
        print("INFO: Parsing receipt...")
        structured = parse_receipt(ocr_payload)
        bill_generated_at = _extract_bill_datetime(structured)

        # Receipt totals:
        # Your mobile app currently sends `amount_paid=0`, so we must derive totals from OCR output.
        receipt_items = structured.get("items", []) or []
        receipt_subtotal = structured.get("subtotal", 0) or 0
        receipt_total_amount = structured.get("total_amount")
        receipt_tax = structured.get("total_tax")
        if receipt_tax is None:
            # The parser uses `tax` in some cases.
            receipt_tax = structured.get("tax")

        # Compute total from items if the parser didn't produce totals.
        if receipt_total_amount is None or float(receipt_total_amount or 0) <= 0:
            receipt_total_amount = sum(float(it.get("total_price", 0) or 0) for it in receipt_items)

        if receipt_total_amount is None:
            receipt_total_amount = float(receipt_subtotal or 0)

        # Prefer the provided payment amount if it is > 0.
        final_total_amount = float(amount_paid) if float(amount_paid or 0) > 0 else float(receipt_total_amount or 0)
        final_total_tax = float(receipt_tax or 0)
        print(
            "INFO: Parsed summary "
            f"items={len(receipt_items)} subtotal={receipt_subtotal} "
            f"parsed_total={receipt_total_amount} final_total={final_total_amount}"
        )
        
        # Categorize items
        for item in structured.get("items", []):
            item_name = (item.get("name") or item.get("product_name") or "").strip()
            if "name" not in item and item.get("product_name"):
                item["name"] = item["product_name"]
            if "product_name" not in item and item.get("name"):
                item["product_name"] = item["name"]
            item["category"] = item.get("category") or categorize_item(item_name)
        
        # Create bill record
        bill = Bill(
            device_id=device_id,
            vendor_id=vendor_id,
            bill_number=structured.get("bill_number"),
            bill_date=structured.get("bill_date"),
            bill_time=structured.get("bill_time"),
            generated_at=bill_generated_at,
            bill_year=bill_generated_at.year,
            bill_month=bill_generated_at.month,
            bill_day=bill_generated_at.day,
            subtotal=structured.get("subtotal", 0),
            total_cgst=structured.get("total_cgst"),
            total_sgst=structured.get("total_sgst"),
            total_tax=final_total_tax,
            total_discount=structured.get("total_discount", 0),
            total_amount=final_total_amount,
            points_added=points_added,
            loyalty_program=loyalty_program,
            shop_type=vendor.shop_type,
            raw_ocr=ocr_payload,
            raw_llm={"source": "parser", **structured},
            receipt_url=f"/uploads/{unique_name}",
            ocr_confidence=structured.get("confidence", 0)
        )
        
        db.add(bill)
        db.commit()
        db.refresh(bill)
        
        print(f"[upload] Bill stored with ID: {bill.id}")
        
        # Add bill items
        for item_data in structured.get("items", []):
            category_name = item_data.get("category", "Other")
            
            # Get or create category
            category = db.query(Category).filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name)
                db.add(category)
                db.commit()
                db.refresh(category)
            
            # Create bill item
            product_name = (
                item_data.get("name")
                or item_data.get("product_name")
                or ""
            ).strip()
            qty = _safe_float(item_data.get("quantity"), 1.0)
            unit_price = _safe_float(item_data.get("unit_price"), 0.0)
            subtotal = _safe_float(item_data.get("subtotal"), qty * unit_price)
            total_price = _safe_float(item_data.get("total_price"), subtotal)

            if not product_name:
                product_name = "Unlabeled item"

            bill_item = BillItem(
                bill_id=bill.id,
                product_name=product_name,
                product_code=item_data.get("product_code"),
                sku=item_data.get("sku"),
                category_id=category.id,
                quantity=qty,
                unit=item_data.get("unit"),
                unit_price=unit_price,
                subtotal=subtotal,
                cgst_rate=item_data.get("cgst_rate"),
                sgst_rate=item_data.get("sgst_rate"),
                cgst_amount=item_data.get("cgst_amount"),
                sgst_amount=item_data.get("sgst_amount"),
                total_tax=item_data.get("total_tax") if item_data.get("total_tax") is not None else item_data.get("tax"),
                total_price=total_price,
                item_discount=float(item_data.get("discount", 0)),
                hsn_code=item_data.get("hsn_code")
            )
            
            db.add(bill_item)
        
        db.commit()
        
        # Store payment details
        payment = PaymentDetail(
            bill_id=bill.id,
            payment_method=payment_method,
            amount_paid=final_total_amount,
            payment_status="completed"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        print(f"[upload] Bill processing completed. Items: {len(structured.get('items', []))}")
        
        # Update vendor stats
        vendor.total_bills_recorded += 1
        db.commit()
        
        return {
            "success": True,
            "bill_id": bill.id,
            "device_id": device_id,
            "vendor_id": vendor_id,
            "merchant": vendor.vendor_name,
            "bill_date": structured.get("bill_date"),
            "bill_number": structured.get("bill_number"),
            "items": structured.get("items", []),
            "total_amount": float(bill.total_amount),
            "items_count": len(structured.get("items", [])),
            "points_added": points_added,
            "message": "Bill processed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[upload] Bill upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bill processing failed: {str(e)}"
        )
    finally:
        db.close()


@router.get("/{bill_id}", response_model=BillDetailedResponse)
async def get_bill(bill_id: int) -> BillDetailedResponse:
    """Get complete bill details with items and payment info."""
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter_by(id=bill_id).first()
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found"
            )
        
        vendor = db.query(Vendor).filter_by(id=bill.vendor_id).first()
        items = db.query(BillItem).filter_by(bill_id=bill_id).all()
        payment = db.query(PaymentDetail).filter_by(bill_id=bill_id).first()
        
        response = BillDetailedResponse(
            **BillResponse.from_orm(bill).dict(),
            vendor=vendor,
            items=[BillItemResponse.from_orm(i) for i in items],
            payment=PaymentDetailResponse.from_orm(payment) if payment else None
        )
        
        return response
        
    finally:
        db.close()


@router.get("/device/{device_id}")
async def get_device_bills(
    device_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    bill_status: str = Query(None),
    year: int = Query(None, ge=2000, le=9999),
    month: int = Query(None, ge=1, le=12),
    day: int = Query(None, ge=1, le=31),
    from_datetime: datetime = Query(None),
    to_datetime: datetime = Query(None)
) -> Dict[str, Any]:
    """Get all bills for a specific device."""
    db = SessionLocal()
    try:
        query = db.query(Bill).filter_by(device_id=device_id)
        
        if bill_status:
            query = query.filter_by(bill_status=bill_status)

        if year is not None:
            query = query.filter(Bill.bill_year == year)
        if month is not None:
            query = query.filter(Bill.bill_month == month)
        if day is not None:
            query = query.filter(Bill.bill_day == day)
        if from_datetime is not None:
            query = query.filter(Bill.generated_at >= from_datetime)
        if to_datetime is not None:
            query = query.filter(Bill.generated_at <= to_datetime)
        
        total = query.count()
        bills = query.order_by(Bill.created_at.desc()).offset(skip).limit(limit).all()
        items = [BillResponse.from_orm(b) for b in bills]
        page = (skip // limit) + 1 if limit > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
        }
        
    finally:
        db.close()


@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(bill_id: int, bill_data: BillCreate) -> BillResponse:
    """Update bill information."""
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter_by(id=bill_id).first()
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found"
            )
        
        update_data = bill_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(bill, field, value)
        
        db.commit()
        db.refresh(bill)
        
        return BillResponse.from_orm(bill)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/{bill_id}")
async def delete_bill(bill_id: int) -> Dict[str, str]:
    """Delete a bill record."""
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter_by(id=bill_id).first()
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found"
            )
        
        # Delete related items and payment
        db.query(BillItem).filter_by(bill_id=bill_id).delete()
        db.query(PaymentDetail).filter_by(bill_id=bill_id).delete()
        db.delete(bill)
        db.commit()
        
        return {"message": "Bill deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
