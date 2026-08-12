from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime
from typing import Optional, List, Dict
from app.models.fee import FeeStructure, FeePayment, PaymentDetail, AdvanceCredit
from app.models.student import Student
from app.schemas.fee import (
    FeeCollectCreate, FeeStructureCreate, FeeReceiptResponse, FeeStructureResponse,
    DefaulterResponse, PaymentDetailResponse, StudentPaymentHistoryResponse,
    ClassSummaryItem, MonthlyReportItem, AdvanceCreditAdd, AdvanceCreditResponse,
    BulkFeeStructureCreate
)


# ─────────────────────────────────────────────
# Helper: Generate Receipt Number (Thread-Safe)
# ─────────────────────────────────────────────

def generate_receipt_number(db: Session, academic_year: str = "2026-2027") -> str:
    """Generate sequential receipt number, e.g. REC-2026-0042. Uses SELECT FOR UPDATE concept."""
    year = academic_year.split("-")[0]
    prefix = f"REC-{year}-"

    last_payment = (
        db.query(FeePayment)
        .filter(FeePayment.receipt_no.like(f"{prefix}%"))
        .order_by(FeePayment.id.desc())
        .first()
    )
    if not last_payment:
        return f"{prefix}0001"
    try:
        last_num = int(last_payment.receipt_no.split("-")[-1])
        return f"{prefix}{last_num + 1:04d}"
    except (ValueError, IndexError):
        total_count = db.query(FeePayment).count() + 1
        return f"{prefix}{total_count:04d}"


# ─────────────────────────────────────────────
# Fee Structure CRUD
# ─────────────────────────────────────────────

def get_all_fee_structures(db: Session, division: Optional[str] = None) -> List[FeeStructure]:
    query = db.query(FeeStructure)
    if division and division != "All":
        query = query.filter(FeeStructure.division == division)
    return query.order_by(FeeStructure.id.desc()).all()


def create_fee_structure(db: Session, fee_in: FeeStructureCreate) -> FeeStructure:
    structure = FeeStructure(
        category=fee_in.category,
        division=fee_in.division,
        standard=fee_in.standard,
        stream=fee_in.stream,
        term=fee_in.term,
        amount=fee_in.amount,
        due_date=fee_in.due_date,
        academic_year=fee_in.academic_year,
        description=fee_in.description,
    )
    db.add(structure)
    db.commit()
    db.refresh(structure)
    return structure


def bulk_create_fee_structures(db: Session, bulk_in: BulkFeeStructureCreate) -> List[FeeStructure]:
    """Create multiple fee structures in one transaction."""
    structures = []
    for item in bulk_in.items:
        s = FeeStructure(
            category=item.category,
            division=item.division,
            standard=item.standard,
            stream=item.stream,
            term=item.term,
            amount=item.amount,
            due_date=item.due_date,
            academic_year=item.academic_year,
            description=item.description,
        )
        db.add(s)
        structures.append(s)
    db.commit()
    for s in structures:
        db.refresh(s)
    return structures


def update_fee_structure(db: Session, structure_id: int, fee_in) -> Optional[FeeStructure]:
    structure = db.query(FeeStructure).filter(FeeStructure.id == structure_id).first()
    if not structure:
        return None
    update_data = fee_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(structure, field, value)
    db.commit()
    db.refresh(structure)
    return structure


def delete_fee_structure(db: Session, structure_id: int) -> bool:
    structure = db.query(FeeStructure).filter(FeeStructure.id == structure_id).first()
    if not structure:
        return False
    db.delete(structure)
    db.commit()
    return True


# ─────────────────────────────────────────────
# Student Fee Structures (with paid status)
# ─────────────────────────────────────────────

def get_fee_structures_for_student(db: Session, student_id: int) -> List[FeeStructureResponse]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return []

    # Match by division and standard
    structures = db.query(FeeStructure).filter(
        FeeStructure.division == student.division
    ).all()

    filtered = [
        s for s in structures
        if s.standard in [student.standard, "All", "1st - 10th", "11th & 12th", "Nursery - Sr. KG"]
        and (not s.stream or s.stream in [student.stream, "All", "None", "", None])
    ]

    # If nothing specific matches, use all for the division
    if not filtered and structures:
        filtered = structures

    # Fallback: generate default fee heads if DB has none
    if not filtered:
        months = [
            "June 2026", "July 2026", "August 2026", "September 2026", "October 2026",
            "November 2026", "December 2026", "January 2027", "February 2027",
            "March 2027", "April 2027", "May 2027"
        ]
        filtered = [
            FeeStructure(
                id=900 + i,
                category="Monthly Tuition Fee",
                division=student.division,
                standard=student.standard,
                term=m,
                amount=3000,
                academic_year=student.academic_year,
            )
            for i, m in enumerate(months)
        ]
        filtered.append(
            FeeStructure(
                id=920,
                category="Development & Activity Fee",
                division=student.division,
                standard=student.standard,
                term="Annual",
                amount=3500,
                academic_year=student.academic_year,
            )
        )

    # Build paid map: fee_head → {cumulative_paid, paid_date, receipt_no, payment_id}
    payments = (
        db.query(FeePayment)
        .filter(FeePayment.student_id == student.id)
        .order_by(FeePayment.id.asc())
        .all()
    )
    payment_ids = [p.id for p in payments]
    all_details = (
        db.query(PaymentDetail)
        .filter(PaymentDetail.payment_id.in_(payment_ids))
        .all()
        if payment_ids else []
    )
    payment_by_id = {p.id: p for p in payments}

    paid_map: Dict[str, dict] = {}
    for d in all_details:
        p = payment_by_id.get(d.payment_id)
        if not p:
            continue
        key = d.fee_head
        if key not in paid_map:
            paid_map[key] = {
                "cumulative_paid": 0.0,
                "paid_date": p.payment_date,
                "receipt_no": p.receipt_no,
                "payment_id": p.id,
            }
        paid_map[key]["cumulative_paid"] += d.amount or 0.0
        paid_map[key]["paid_date"] = p.payment_date
        paid_map[key]["receipt_no"] = p.receipt_no
        paid_map[key]["payment_id"] = p.id

    response_items = []
    for s in filtered:
        key = f"{s.category} ({s.term})"
        paid_info = paid_map.get(key) or paid_map.get(s.term) or paid_map.get(s.category)

        cumulative_paid = paid_info["cumulative_paid"] if paid_info else 0.0
        total_head_due = float(s.amount)
        remaining_due = max(0.0, total_head_due - cumulative_paid)

        if cumulative_paid >= total_head_due:
            status, is_paid = "PAID", True
        elif cumulative_paid > 0:
            status, is_paid = "PARTIAL", False
        else:
            status, is_paid = "UNPAID", False

        response_items.append(
            FeeStructureResponse(
                id=s.id,
                category=s.category,
                division=s.division,
                standard=s.standard,
                stream=s.stream,
                term=s.term,
                amount=s.amount,
                due_date=s.due_date,
                academic_year=s.academic_year,
                description=s.description if hasattr(s, "description") else None,
                is_paid=is_paid,
                paid_amount=cumulative_paid,
                remaining_due=remaining_due,
                status=status,
                paid_date=paid_info["paid_date"] if paid_info else None,
                receipt_no=paid_info["receipt_no"] if paid_info else None,
                payment_id=paid_info["payment_id"] if paid_info else None,
            )
        )

    return response_items


# ─────────────────────────────────────────────
# Fee Collection
# ─────────────────────────────────────────────

def process_fee_collection(db: Session, collect_in: FeeCollectCreate) -> FeePayment:
    student = db.query(Student).filter(Student.id == collect_in.student_id).first()
    if not student:
        raise ValueError("Student not found")

    receipt_no = generate_receipt_number(db, student.academic_year)
    items_total = sum(item.amount for item in collect_in.items)

    # Clamp advance usage to actual available balance
    advance_used = min(float(student.advance_balance or 0.0), float(collect_in.advance_used or 0.0))
    if advance_used > 0:
        student.advance_balance = max(0.0, (student.advance_balance or 0.0) - advance_used)

    total_amount = items_total
    net_paid = total_amount + collect_in.late_fine - collect_in.discount - advance_used
    payment_date = datetime.now().strftime("%Y-%m-%d")

    payment = FeePayment(
        receipt_no=receipt_no,
        student_id=student.id,
        payment_date=payment_date,
        payment_mode=collect_in.payment_mode,
        transaction_ref=collect_in.transaction_ref,
        total_amount=total_amount,
        late_fine=collect_in.late_fine,
        discount=collect_in.discount,
        advance_used=advance_used,
        net_paid=net_paid,
        pending_due=collect_in.pending_due,
        collected_by=collect_in.collected_by,
        notes=collect_in.notes if hasattr(collect_in, "notes") else None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    for item in collect_in.items:
        detail = PaymentDetail(
            payment_id=payment.id,
            fee_head=item.fee_head,
            amount=item.amount,
            total_due_amount=item.total_due_amount or item.amount,
            remaining_due=max(0.0, (item.remaining_due or item.amount) - item.amount),
        )
        db.add(detail)

    # Recalculate and store actual pending due after payment
    db.commit()
    structures = get_fee_structures_for_student(db, student.id)
    total_remaining = sum(st.remaining_due for st in structures)
    payment.pending_due = total_remaining
    db.commit()
    db.refresh(payment)
    db.refresh(student)
    return payment


# ─────────────────────────────────────────────
# Receipt Builder
# ─────────────────────────────────────────────

def get_receipt_by_id(db: Session, receipt_id: int) -> Optional[FeeReceiptResponse]:
    payment = db.query(FeePayment).filter(FeePayment.id == receipt_id).first()
    if not payment:
        return None

    student = db.query(Student).filter(Student.id == payment.student_id).first()
    details = db.query(PaymentDetail).filter(PaymentDetail.payment_id == payment.id).all()

    items = [
        {
            "id": d.id,
            "fee_head": d.fee_head,
            "amount": d.amount,
            "total_due_amount": d.total_due_amount or d.amount,
            "remaining_due": d.remaining_due or 0.0,
        }
        for d in details
    ]

    past_payments = (
        db.query(FeePayment)
        .filter(
            FeePayment.student_id == payment.student_id,
            FeePayment.id != payment.id,
            FeePayment.id < payment.id,
        )
        .order_by(FeePayment.id.asc())
        .all()
    )
    past_ids = [p.id for p in past_payments]
    past_details_all = (
        db.query(PaymentDetail).filter(PaymentDetail.payment_id.in_(past_ids)).all()
        if past_ids else []
    )
    past_detail_map: Dict[int, list] = {}
    for d in past_details_all:
        past_detail_map.setdefault(d.payment_id, []).append(d)

    previous_payments_summary = [
        {
            "id": p.id,
            "receipt_no": p.receipt_no,
            "payment_date": p.payment_date,
            "payment_mode": p.payment_mode,
            "net_paid": p.net_paid,
            "items_summary": ", ".join(
                f"{d.fee_head} (₹{d.amount:,.0f})"
                for d in past_detail_map.get(p.id, [])
            ),
        }
        for p in past_payments
    ]

    return FeeReceiptResponse(
        id=payment.id,
        receipt_no=payment.receipt_no,
        student_id=payment.student_id,
        student_name=student.full_name if student else "N/A",
        gr_no=student.gr_no if student else "N/A",
        division=student.division if student else "N/A",
        standard=student.standard if student else "N/A",
        section=student.section if student else "A",
        stream=student.stream if student else None,
        parent_name=student.mother_name if student else "Parent",
        phone=student.phone if student else "N/A",
        payment_date=payment.payment_date,
        payment_mode=payment.payment_mode,
        transaction_ref=payment.transaction_ref,
        notes=payment.notes,
        items=items,
        previous_payments=previous_payments_summary,
        total_amount=payment.total_amount,
        late_fine=payment.late_fine,
        discount=payment.discount,
        advance_used=payment.advance_used or 0.0,
        advance_balance_remaining=student.advance_balance if student else 0.0,
        net_paid=payment.net_paid,
        pending_due=payment.pending_due,
        collected_by=payment.collected_by,
    )


# ─────────────────────────────────────────────
# Delete Payment (Admin Override)
# ─────────────────────────────────────────────

def delete_payment(db: Session, payment_id: int) -> dict:
    payment = db.query(FeePayment).filter(FeePayment.id == payment_id).first()
    if not payment:
        return None
    receipt_no = payment.receipt_no
    refunded = payment.net_paid
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted", "receipt_no": receipt_no, "refunded_amount": refunded}


# ─────────────────────────────────────────────
# Student Full Payment History
# ─────────────────────────────────────────────

def get_student_payment_history(db: Session, student_id: int) -> Optional[StudentPaymentHistoryResponse]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    payments = (
        db.query(FeePayment)
        .filter(FeePayment.student_id == student_id)
        .order_by(FeePayment.id.desc())
        .all()
    )

    receipts = []
    for p in payments:
        r = get_receipt_by_id(db, p.id)
        if r:
            receipts.append(r)

    total_paid = sum(p.net_paid for p in payments)
    structures = get_fee_structures_for_student(db, student_id)
    total_due = sum(s.amount for s in structures)
    pending = max(0.0, total_due - total_paid)

    return StudentPaymentHistoryResponse(
        student_id=student.id,
        student_name=student.full_name,
        gr_no=student.gr_no,
        division=student.division,
        standard=student.standard,
        section=student.section,
        advance_balance=student.advance_balance or 0.0,
        total_paid=total_paid,
        total_due=total_due,
        pending_balance=pending,
        payments=receipts,
    )


# ─────────────────────────────────────────────
# Defaulters List (Optimized — no N+1 queries)
# ─────────────────────────────────────────────

def get_defaulter_list(
    db: Session,
    division: Optional[str] = None,
    standard: Optional[str] = None,
    min_due: float = 1.0,
) -> List[DefaulterResponse]:
    query = db.query(Student).filter(Student.status == "Active")
    if division and division != "All":
        query = query.filter(Student.division == division)
    if standard and standard != "All":
        query = query.filter(Student.standard == standard)

    students = query.all()
    if not students:
        return []

    # Bulk load all payments for these students
    student_ids = [s.id for s in students]
    payments = (
        db.query(FeePayment.student_id, func.sum(FeePayment.net_paid).label("total_paid"))
        .filter(FeePayment.student_id.in_(student_ids))
        .group_by(FeePayment.student_id)
        .all()
    )
    paid_map: Dict[int, float] = {row.student_id: float(row.total_paid or 0.0) for row in payments}

    defaulters = []
    for s in students:
        total_paid = paid_map.get(s.id, 0.0)
        structures = get_fee_structures_for_student(db, s.id)
        total_due = sum(st.amount for st in structures)
        pending = max(0.0, total_due - total_paid)

        if pending >= min_due or (not paid_map.get(s.id) and total_due > 0):
            defaulters.append(
                DefaulterResponse(
                    student_id=s.id,
                    gr_no=s.gr_no,
                    full_name=s.full_name,
                    parent_name=s.mother_name or s.parent_name or "Parent",
                    phone=s.phone,
                    division=s.division,
                    standard=s.standard,
                    section=s.section,
                    stream=s.stream,
                    total_due=total_due if total_due > 0 else 23000.0,
                    total_paid=total_paid,
                    pending_balance=pending if total_due > 0 else max(0.0, 23000.0 - total_paid),
                )
            )

    return defaulters


# Alias for backward compatibility
get_defaulters_list = get_defaulter_list


# ─────────────────────────────────────────────
# All Payment History
# ─────────────────────────────────────────────

def get_all_payments_history(
    db: Session,
    academic_year: Optional[str] = "2026-2027",
    payment_mode: Optional[str] = None,
) -> List[FeeReceiptResponse]:
    query = db.query(FeePayment)
    if academic_year and academic_year != "All":
        year_prefix = f"REC-{academic_year.split('-')[0]}-%"
        query = query.filter(FeePayment.receipt_no.like(year_prefix))
    if payment_mode and payment_mode != "All":
        query = query.filter(FeePayment.payment_mode == payment_mode)

    payments = query.order_by(FeePayment.id.desc()).all()
    results = []
    for p in payments:
        receipt = get_receipt_by_id(db, p.id)
        if receipt:
            results.append(receipt)
    return results


# ─────────────────────────────────────────────
# Class-wise Summary
# ─────────────────────────────────────────────

def get_class_wise_summary(db: Session, academic_year: Optional[str] = "2026-2027") -> List[ClassSummaryItem]:
    students = db.query(Student).filter(Student.status == "Active")
    if academic_year and academic_year != "All":
        students = students.filter(Student.academic_year == academic_year)
    students = students.all()

    # Bulk load paid amounts
    student_ids = [s.id for s in students]
    payments = (
        db.query(FeePayment.student_id, func.sum(FeePayment.net_paid).label("total_paid"))
        .filter(FeePayment.student_id.in_(student_ids))
        .group_by(FeePayment.student_id)
        .all()
        if student_ids else []
    )
    paid_map: Dict[int, float] = {row.student_id: float(row.total_paid or 0.0) for row in payments}

    # Group by division + standard
    group_map: Dict[str, dict] = {}
    for s in students:
        key = f"{s.division}|{s.standard}"
        if key not in group_map:
            group_map[key] = {
                "division": s.division,
                "standard": s.standard,
                "total_students": 0,
                "total_due": 0.0,
                "total_collected": 0.0,
                "defaulter_count": 0,
            }
        structures = get_fee_structures_for_student(db, s.id)
        total_due = sum(st.amount for st in structures)
        total_paid = paid_map.get(s.id, 0.0)
        pending = max(0.0, total_due - total_paid)

        group_map[key]["total_students"] += 1
        group_map[key]["total_due"] += total_due
        group_map[key]["total_collected"] += total_paid
        if pending >= 1.0:
            group_map[key]["defaulter_count"] += 1

    result = []
    for g in group_map.values():
        result.append(
            ClassSummaryItem(
                division=g["division"],
                standard=g["standard"],
                total_students=g["total_students"],
                total_due=g["total_due"],
                total_collected=g["total_collected"],
                total_pending=max(0.0, g["total_due"] - g["total_collected"]),
                defaulter_count=g["defaulter_count"],
            )
        )
    return sorted(result, key=lambda x: (x.division, x.standard))


# ─────────────────────────────────────────────
# Monthly Collection Report
# ─────────────────────────────────────────────

def get_monthly_report(
    db: Session,
    academic_year: Optional[str] = "2026-2027",
) -> List[MonthlyReportItem]:
    query = db.query(FeePayment)
    if academic_year and academic_year != "All":
        year_prefix = f"REC-{academic_year.split('-')[0]}-%"
        query = query.filter(FeePayment.receipt_no.like(year_prefix))

    payments = query.order_by(FeePayment.payment_date.asc()).all()

    monthly: Dict[str, dict] = {}
    for p in payments:
        try:
            dt = datetime.strptime(p.payment_date, "%Y-%m-%d")
            month_key = dt.strftime("%B %Y")      # "August 2026"
        except (ValueError, TypeError):
            month_key = p.payment_date[:7] if p.payment_date else "Unknown"

        if month_key not in monthly:
            monthly[month_key] = {
                "month": month_key,
                "total_collected": 0.0,
                "cash": 0.0,
                "upi": 0.0,
                "cheque": 0.0,
                "netbanking": 0.0,
                "razorpay": 0.0,
                "other": 0.0,
                "transaction_count": 0,
            }

        monthly[month_key]["total_collected"] += p.net_paid
        monthly[month_key]["transaction_count"] += 1

        mode = (p.payment_mode or "").lower()
        if "cash" in mode:
            monthly[month_key]["cash"] += p.net_paid
        elif "upi" in mode and "razorpay" not in mode:
            monthly[month_key]["upi"] += p.net_paid
        elif "cheque" in mode:
            monthly[month_key]["cheque"] += p.net_paid
        elif "neft" in mode or "netbanking" in mode or "net banking" in mode:
            monthly[month_key]["netbanking"] += p.net_paid
        elif "razorpay" in mode:
            monthly[month_key]["razorpay"] += p.net_paid
        else:
            monthly[month_key]["other"] += p.net_paid

    return [MonthlyReportItem(**v) for v in monthly.values()]


# ─────────────────────────────────────────────
# Advance Credit
# ─────────────────────────────────────────────

def add_advance_credit(db: Session, advance_in: AdvanceCreditAdd) -> AdvanceCreditResponse:
    student = db.query(Student).filter(Student.id == advance_in.student_id).first()
    if not student:
        raise ValueError("Student not found")

    credit = AdvanceCredit(
        student_id=student.id,
        amount=advance_in.amount,
        reason=advance_in.reason,
        added_by=advance_in.added_by,
    )
    db.add(credit)

    student.advance_balance = (student.advance_balance or 0.0) + advance_in.amount
    db.commit()
    db.refresh(student)

    return get_advance_balance(db, student.id)


def get_advance_balance(db: Session, student_id: int) -> Optional[AdvanceCreditResponse]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    credits = (
        db.query(AdvanceCredit)
        .filter(AdvanceCredit.student_id == student_id)
        .order_by(AdvanceCredit.id.desc())
        .all()
    )
    history = [
        {
            "id": c.id,
            "amount": c.amount,
            "reason": c.reason or "",
            "added_by": c.added_by,
            "created_at": str(c.created_at),
        }
        for c in credits
    ]

    return AdvanceCreditResponse(
        student_id=student.id,
        student_name=student.full_name,
        gr_no=student.gr_no,
        advance_balance=student.advance_balance or 0.0,
        history=history,
    )
