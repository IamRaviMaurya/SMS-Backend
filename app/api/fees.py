from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.core.database import get_db
from app.schemas.fee import (
    FeeStructureCreate, FeeStructureUpdate, FeeStructureResponse,
    FeeCollectCreate, FeeReceiptResponse, DefaulterResponse
)
from app.models.fee import FeePayment, FeeStructure
from app.models.student import Student
from app.services import fee_service

router = APIRouter(prefix="/fees", tags=["Fees"])

@router.get("/structures/all", response_model=List[FeeStructureResponse])
def get_all_structures(division: Optional[str] = Query(None), db: Session = Depends(get_db)):
    return fee_service.get_all_fee_structures(db, division=division)

@router.post("/structures", response_model=FeeStructureResponse)
def create_structure(fee_in: FeeStructureCreate, db: Session = Depends(get_db)):
    return fee_service.create_fee_structure(db, fee_in)

@router.put("/structures/{structure_id}", response_model=FeeStructureResponse)
def update_structure(structure_id: int, fee_in: FeeStructureUpdate, db: Session = Depends(get_db)):
    updated = fee_service.update_fee_structure(db, structure_id, fee_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    return updated

@router.delete("/structures/{structure_id}")
def delete_structure(structure_id: int, db: Session = Depends(get_db)):
    deleted = fee_service.delete_fee_structure(db, structure_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    return {"message": "Fee structure head deleted successfully"}

@router.get("/structures/student/{student_id}", response_model=List[FeeStructureResponse])
def get_student_fee_structures(student_id: int, db: Session = Depends(get_db)):
    return fee_service.get_fee_structures_for_student(db, student_id)

@router.post("/collect", response_model=FeeReceiptResponse)
def collect_fee(collect_in: FeeCollectCreate, db: Session = Depends(get_db)):
    """
    Fast Fee Collection Desk API:
    Calculates total, applies late fine/discount, creates FeePayment & PaymentDetail records,
    and returns full print-ready receipt.
    """
    try:
        payment = fee_service.process_fee_collection(db, collect_in)
        receipt = fee_service.get_receipt_by_id(db, payment.id)
        return receipt
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/receipt/{receipt_id}", response_model=FeeReceiptResponse)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """
    Retrieve Printable Fee Receipt details by ID.
    """
    receipt = fee_service.get_receipt_by_id(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@router.get("/defaulters", response_model=List[DefaulterResponse])
def get_defaulters(
    division: Optional[str] = Query(None),
    standard: Optional[str] = Query(None),
    min_due: float = Query(1.0, description="Minimum pending balance filter"),
    db: Session = Depends(get_db)
):
    """
    Defaulter list generation with pending balance filters.
    """
    return fee_service.get_defaulter_list(db, division=division, standard=standard, min_due=min_due)

@router.get("/payments/all", response_model=List[FeeReceiptResponse])
def get_all_payments(
    academic_year: Optional[str] = Query("2026-2027"),
    payment_mode: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return fee_service.get_all_payments_history(db, academic_year=academic_year, payment_mode=payment_mode)

@router.get("/stats")
def get_fee_stats(academic_year: Optional[str] = Query("2026-2027"), db: Session = Depends(get_db)):
    student_query = db.query(Student).filter(Student.status == "Active")
    if academic_year and academic_year != "All":
        student_query = student_query.filter(Student.academic_year == academic_year)
    total_students = student_query.count()

    payment_query = db.query(FeePayment)
    if academic_year and academic_year != "All":
        year_prefix = f"REC-{academic_year.split('-')[0]}-%"
        payment_query = payment_query.filter(FeePayment.receipt_no.like(year_prefix))
        
    total_collected = payment_query.with_entities(func.sum(FeePayment.net_paid)).scalar() or 0.0
    total_receipts = payment_query.count()
    
    # Calculate defaulters for selected academic year
    defaulters = fee_service.get_defaulter_list(db, min_due=1.0)
    total_pending = sum(d.pending_balance for d in defaulters)
    
    return {
        "academic_year": academic_year,
        "total_collected": total_collected,
        "total_receipts": total_receipts,
        "total_students": total_students,
        "total_pending": total_pending,
        "defaulter_count": len(defaulters)
    }
