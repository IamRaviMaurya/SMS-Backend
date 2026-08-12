from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ─────────────────────────────────────────────
# Fee Structure Schemas
# ─────────────────────────────────────────────

class FeeStructureBase(BaseModel):
    category: str = Field(..., example="Tuition Fee")
    division: str = Field(..., example="School Section")
    standard: str = Field(..., example="7th")
    stream: Optional[str] = Field(None, example="Science")
    term: str = Field(..., example="Term 1")
    amount: float = Field(..., example=15000.0)
    due_date: Optional[str] = Field(None, example="2026-09-30")
    academic_year: str = Field("2026-2027", example="2026-2027")
    description: Optional[str] = Field(None, example="Monthly Tuition for June 2026")


class FeeStructureCreate(FeeStructureBase):
    pass


class FeeStructureUpdate(BaseModel):
    category: Optional[str] = None
    division: Optional[str] = None
    standard: Optional[str] = None
    stream: Optional[str] = None
    term: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    academic_year: Optional[str] = None
    description: Optional[str] = None


class FeeStructureResponse(FeeStructureBase):
    id: int
    is_paid: Optional[bool] = False
    paid_amount: Optional[float] = 0.0
    remaining_due: Optional[float] = 0.0
    status: Optional[str] = "UNPAID"   # "PAID", "PARTIAL", "UNPAID"
    paid_date: Optional[str] = None
    receipt_no: Optional[str] = None
    payment_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkFeeStructureCreate(BaseModel):
    """Create multiple fee structures in one request (e.g. all months for a class)."""
    items: List[FeeStructureCreate]


# ─────────────────────────────────────────────
# Fee Collection Schemas
# ─────────────────────────────────────────────

class FeeItemCollect(BaseModel):
    fee_head: str
    amount: float                               # Amount collecting now
    total_due_amount: Optional[float] = 0.0
    remaining_due: Optional[float] = 0.0


class FeeCollectCreate(BaseModel):
    student_id: int
    payment_mode: str = Field(..., example="UPI")   # Cash, UPI, Cheque, NetBanking, Razorpay
    transaction_ref: Optional[str] = Field(None, example="UPI9876543210")
    items: List[FeeItemCollect]
    late_fine: float = Field(0.0, example=200.0)
    discount: float = Field(0.0, example=0.0)
    advance_used: float = Field(0.0, example=0.0)
    pending_due: float = Field(0.0, example=5000.0)
    collected_by: str = Field("Accounts Counter", example="Counter Admin")
    notes: Optional[str] = Field(None, example="Paid via GPay")


# ─────────────────────────────────────────────
# Receipt Schemas
# ─────────────────────────────────────────────

class PaymentDetailResponse(BaseModel):
    id: int
    fee_head: str
    amount: float
    total_due_amount: Optional[float] = 0.0
    remaining_due: Optional[float] = 0.0

    class Config:
        from_attributes = True


class PreviousPaymentSummary(BaseModel):
    id: int
    receipt_no: str
    payment_date: str
    payment_mode: str
    net_paid: float
    items_summary: str

    class Config:
        from_attributes = True


class FeeReceiptResponse(BaseModel):
    id: int
    receipt_no: str
    student_id: int
    student_name: str
    gr_no: str
    division: str
    standard: str
    section: str
    stream: Optional[str] = None
    parent_name: str
    phone: str

    payment_date: str
    payment_mode: str
    transaction_ref: Optional[str] = None
    notes: Optional[str] = None

    total_amount: float
    late_fine: float
    discount: float
    advance_used: Optional[float] = 0.0
    advance_balance_remaining: Optional[float] = 0.0
    net_paid: float
    pending_due: float
    collected_by: str

    items: List[PaymentDetailResponse]
    previous_payments: List[PreviousPaymentSummary] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Defaulter Schema
# ─────────────────────────────────────────────

class DefaulterResponse(BaseModel):
    student_id: int
    gr_no: str
    full_name: str
    parent_name: str
    phone: str
    division: str
    standard: str
    section: str
    stream: Optional[str] = None
    total_due: float
    total_paid: float
    pending_balance: float

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Student Payment History Schema
# ─────────────────────────────────────────────

class StudentPaymentHistoryResponse(BaseModel):
    student_id: int
    student_name: str
    gr_no: str
    division: str
    standard: str
    section: str
    advance_balance: float
    total_paid: float
    total_due: float
    pending_balance: float
    payments: List[FeeReceiptResponse]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Class-wise Summary Schema
# ─────────────────────────────────────────────

class ClassSummaryItem(BaseModel):
    division: str
    standard: str
    total_students: int
    total_due: float
    total_collected: float
    total_pending: float
    defaulter_count: int

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Monthly Report Schema
# ─────────────────────────────────────────────

class MonthlyReportItem(BaseModel):
    month: str          # e.g. "August 2026"
    total_collected: float
    cash: float
    upi: float
    cheque: float
    netbanking: float
    razorpay: float
    other: float
    transaction_count: int

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Advance Credit Schemas
# ─────────────────────────────────────────────

class AdvanceCreditAdd(BaseModel):
    student_id: int
    amount: float = Field(..., example=5000.0)
    reason: Optional[str] = Field(None, example="Overpayment refund credit")
    added_by: str = Field("Admin", example="Principal")


class AdvanceCreditResponse(BaseModel):
    student_id: int
    student_name: str
    gr_no: str
    advance_balance: float
    history: List[dict] = []

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Delete Payment Response
# ─────────────────────────────────────────────

class DeletePaymentResponse(BaseModel):
    message: str
    receipt_no: str
    refunded_amount: float
