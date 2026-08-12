from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False) # Tuition Fee, Development Fee, Transport Fee, Term Fee
    division = Column(String(50), nullable=False) # Pre-Primary, School Section, Junior College
    standard = Column(String(50), nullable=False) # Nursery..12th, or "All"
    stream = Column(String(50), nullable=True)    # Science, Commerce, Arts or "All"
    term = Column(String(50), nullable=False)      # Term 1, Term 2, Annual
    amount = Column(Float, nullable=False)
    due_date = Column(String(20), nullable=True)   # YYYY-MM-DD
    academic_year = Column(String(20), nullable=False, default="2026-2027")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FeePayment(Base):
    __tablename__ = "fee_payments"

    id = Column(Integer, primary_key=True, index=True)
    receipt_no = Column(String(50), unique=True, index=True, nullable=False) # REC-2026-0001
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    payment_date = Column(String(20), nullable=False) # YYYY-MM-DD
    payment_mode = Column(String(50), nullable=False) # Cash, UPI, Cheque, NetBanking
    transaction_ref = Column(String(100), nullable=True)
    
    total_amount = Column(Float, nullable=False)
    late_fine = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    advance_used = Column(Float, nullable=False, default=0.0) # Advance credit applied
    net_paid = Column(Float, nullable=False)
    pending_due = Column(Float, nullable=False, default=0.0)
    collected_by = Column(String(100), nullable=False, default="Accounts Counter")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student")
    details = relationship("PaymentDetail", back_populates="payment", cascade="all, delete-orphan")


class PaymentDetail(Base):
    __tablename__ = "payment_details"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("fee_payments.id"), nullable=False)
    fee_head = Column(String(100), nullable=False) # Tuition Fee, Transport, etc.
    amount = Column(Float, nullable=False) # Amount paid in this transaction
    total_due_amount = Column(Float, nullable=True, default=0.0) # Total head fee
    remaining_due = Column(Float, nullable=True, default=0.0) # Remaining balance for head

    payment = relationship("FeePayment", back_populates="details")
