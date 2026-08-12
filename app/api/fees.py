from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.core.database import get_db
from app.schemas.fee import (
    FeeStructureCreate, FeeStructureUpdate, FeeStructureResponse,
    FeeCollectCreate, FeeReceiptResponse, DefaulterResponse,
    BulkFeeStructureCreate, StudentPaymentHistoryResponse,
    ClassSummaryItem, MonthlyReportItem, AdvanceCreditAdd, AdvanceCreditResponse,
    DeletePaymentResponse,
)
from app.models.fee import FeePayment, FeeStructure
from app.models.student import Student
from app.services import fee_service

router = APIRouter(prefix="/fees", tags=["Fees"])


# ─────────────────────────────────────────────
# Fee Structures
# ─────────────────────────────────────────────

@router.get("/structures/all", response_model=List[FeeStructureResponse])
def get_all_structures(
    division: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all fee structure heads, optionally filtered by division."""
    return fee_service.get_all_fee_structures(db, division=division)


@router.post("/structures", response_model=FeeStructureResponse)
def create_structure(fee_in: FeeStructureCreate, db: Session = Depends(get_db)):
    """Create a single fee structure head."""
    return fee_service.create_fee_structure(db, fee_in)


@router.post("/structures/bulk", response_model=List[FeeStructureResponse])
def bulk_create_structures(bulk_in: BulkFeeStructureCreate, db: Session = Depends(get_db)):
    """
    Bulk create multiple fee structure heads in a single request.
    Useful for adding 12 monthly fee heads for a class at once.
    """
    return fee_service.bulk_create_fee_structures(db, bulk_in)


@router.put("/structures/{structure_id}", response_model=FeeStructureResponse)
def update_structure(
    structure_id: int,
    fee_in: FeeStructureUpdate,
    db: Session = Depends(get_db),
):
    """Update a fee structure head."""
    updated = fee_service.update_fee_structure(db, structure_id, fee_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    return updated


@router.delete("/structures/{structure_id}")
def delete_structure(structure_id: int, db: Session = Depends(get_db)):
    """Delete a fee structure head."""
    deleted = fee_service.delete_fee_structure(db, structure_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    return {"message": "Fee structure head deleted successfully"}


@router.get("/structures/student/{student_id}", response_model=List[FeeStructureResponse])
def get_student_fee_structures(student_id: int, db: Session = Depends(get_db)):
    """
    Get fee structures applicable for a student with paid/unpaid status.
    Returns each fee head with is_paid, paid_amount, remaining_due, status, receipt_no.
    """
    return fee_service.get_fee_structures_for_student(db, student_id)


# ─────────────────────────────────────────────
# Fee Collection
# ─────────────────────────────────────────────

@router.post("/collect", response_model=FeeReceiptResponse)
def collect_fee(collect_in: FeeCollectCreate, db: Session = Depends(get_db)):
    """
    Fee Collection Desk API:
    Calculates total, applies late fine/discount/advance, creates FeePayment & PaymentDetail records,
    recalculates pending balance, and returns a full print-ready receipt.
    """
    try:
        payment = fee_service.process_fee_collection(db, collect_in)
        receipt = fee_service.get_receipt_by_id(db, payment.id)
        return receipt
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────
# Receipt
# ─────────────────────────────────────────────

@router.get("/receipt/{receipt_id}", response_model=FeeReceiptResponse)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Retrieve printable fee receipt by payment ID."""
    receipt = fee_service.get_receipt_by_id(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


# ─────────────────────────────────────────────
# Defaulters
# ─────────────────────────────────────────────

@router.get("/defaulters", response_model=List[DefaulterResponse])
def get_defaulters(
    division: Optional[str] = Query(None),
    standard: Optional[str] = Query(None),
    min_due: float = Query(1.0, description="Minimum pending balance filter"),
    db: Session = Depends(get_db),
):
    """Defaulter list with pending balance filters. Optimized bulk query version."""
    return fee_service.get_defaulter_list(db, division=division, standard=standard, min_due=min_due)


# ─────────────────────────────────────────────
# Payment History
# ─────────────────────────────────────────────

@router.get("/payments/all", response_model=List[FeeReceiptResponse])
def get_all_payments(
    academic_year: Optional[str] = Query("2026-2027"),
    payment_mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """All payment history, with optional filters for academic year and payment mode."""
    return fee_service.get_all_payments_history(db, academic_year=academic_year, payment_mode=payment_mode)


@router.get("/payments/student/{student_id}", response_model=StudentPaymentHistoryResponse)
def get_student_payment_history(student_id: int, db: Session = Depends(get_db)):
    """
    Full payment history for a specific student:
    - All receipts
    - Total paid / total due / pending balance
    - Current advance balance
    """
    history = fee_service.get_student_payment_history(db, student_id)
    if not history:
        raise HTTPException(status_code=404, detail="Student not found or no payment records")
    return history


@router.delete("/payments/{payment_id}", response_model=DeletePaymentResponse)
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    """
    Admin override: Delete a wrong/duplicate payment entry.
    WARNING: This permanently removes the payment record. Use with caution.
    """
    result = fee_service.delete_payment(db, payment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Payment not found")
    return result


# ─────────────────────────────────────────────
# Reports & Analytics
# ─────────────────────────────────────────────

@router.get("/stats")
def get_fee_stats(
    academic_year: Optional[str] = Query("2026-2027"),
    db: Session = Depends(get_db),
):
    """Dashboard stats: total collected, pending, receipts, defaulter count."""
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

    defaulters = fee_service.get_defaulter_list(db, min_due=1.0)
    total_pending = sum(d.pending_balance for d in defaulters)

    return {
        "academic_year": academic_year,
        "total_collected": round(total_collected, 2),
        "total_receipts": total_receipts,
        "total_students": total_students,
        "total_pending": round(total_pending, 2),
        "defaulter_count": len(defaulters),
    }


@router.get("/summary/class", response_model=List[ClassSummaryItem])
def get_class_wise_summary(
    academic_year: Optional[str] = Query("2026-2027"),
    db: Session = Depends(get_db),
):
    """
    Class-wise fee collection summary:
    Shows total due, collected, pending, and defaulter count per Division + Standard.
    """
    return fee_service.get_class_wise_summary(db, academic_year=academic_year)


@router.get("/monthly-report", response_model=List[MonthlyReportItem])
def get_monthly_report(
    academic_year: Optional[str] = Query("2026-2027"),
    db: Session = Depends(get_db),
):
    """
    Month-wise fee collection report:
    Shows total collected per month broken down by payment mode (Cash, UPI, Cheque, NetBanking, Razorpay).
    """
    return fee_service.get_monthly_report(db, academic_year=academic_year)


# ─────────────────────────────────────────────
# Advance Credit Management
# ─────────────────────────────────────────────

@router.get("/advance/{student_id}", response_model=AdvanceCreditResponse)
def get_advance_balance(student_id: int, db: Session = Depends(get_db)):
    """Get student's current advance credit balance and credit history."""
    result = fee_service.get_advance_balance(db, student_id)
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    return result


@router.post("/advance/add", response_model=AdvanceCreditResponse)
def add_advance_credit(advance_in: AdvanceCreditAdd, db: Session = Depends(get_db)):
    """
    Add advance credit to a student's account.
    This credit can be used to offset future fee payments.
    """
    try:
        return fee_service.add_advance_credit(db, advance_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
