from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional, List
from app.models.fee import FeeStructure, FeePayment, PaymentDetail
from app.models.student import Student
from app.schemas.fee import FeeCollectCreate, FeeStructureCreate, FeeReceiptResponse, FeeStructureResponse, DefaulterResponse, PaymentDetailResponse

def generate_receipt_number(db: Session, academic_year: str = "2026-2027") -> str:
    year = academic_year.split("-")[0]
    prefix = f"REC-{year}-"
    
    last_payment = db.query(FeePayment).filter(FeePayment.receipt_no.like(f"{prefix}%")).order_by(FeePayment.id.desc()).first()
    if not last_payment:
        return f"{prefix}0001"
        
    try:
        last_num = int(last_payment.receipt_no.split("-")[-1])
        new_num = last_num + 1
        return f"{prefix}{new_num:04d}"
    except ValueError:
        total_count = db.query(FeePayment).count() + 1
        return f"{prefix}{total_count:04d}"

def get_fee_structures_for_student(db: Session, student_id: int):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return []
        
    query = db.query(FeeStructure).filter(
        FeeStructure.division == student.division
    )
    
    structures = query.all()
    filtered = []
    for s in structures:
        if s.standard in [student.standard, "All", "1st - 10th", "11th & 12th", "Nursery - Sr. KG"]:
            if not s.stream or s.stream in [student.stream, "All", "None", "", None]:
                filtered.append(s)

    if not filtered and structures:
        filtered = structures

    # Fallback default fee structure if database has 0 fee heads for this division
    if not filtered:
        months = ["June 2026", "July 2026", "August 2026", "September 2026", "October 2026", "November 2026", "December 2026", "January 2027", "February 2027", "March 2027", "April 2027", "May 2027"]
        filtered = [
            FeeStructure(id=900 + i, category="Monthly Tuition Fee", division=student.division, standard=student.standard, term=m, amount=3000, academic_year=student.academic_year)
            for i, m in enumerate(months)
        ]
        filtered.append(
            FeeStructure(id=920, category="Development & Activity Fee", division=student.division, standard=student.standard, term="Annual", amount=3500, academic_year=student.academic_year)
        )

    # Calculate cumulative payments per fee head for this student
    payments = db.query(FeePayment).filter(FeePayment.student_id == student.id).all()
    paid_map = {}
    for p in payments:
        details = db.query(PaymentDetail).filter(PaymentDetail.payment_id == p.id).all()
        for d in details:
            if d.fee_head not in paid_map:
                paid_map[d.fee_head] = {
                    "cumulative_paid": 0.0,
                    "paid_date": p.payment_date,
                    "receipt_no": p.receipt_no,
                    "payment_id": p.id
                }
            paid_map[d.fee_head]["cumulative_paid"] += (d.amount or 0.0)
            paid_map[d.fee_head]["paid_date"] = p.payment_date
            paid_map[d.fee_head]["receipt_no"] = p.receipt_no
            paid_map[d.fee_head]["payment_id"] = p.id

    response_items = []
    for s in filtered:
        key = f"{s.category} ({s.term})"
        paid_info = paid_map.get(key) or paid_map.get(s.term) or paid_map.get(s.category)
        
        cumulative_paid = paid_info["cumulative_paid"] if paid_info else 0.0
        total_head_due = float(s.amount)
        remaining_due = max(0.0, total_head_due - cumulative_paid)
        
        if cumulative_paid >= total_head_due:
            status = "PAID"
            is_paid = True
        elif cumulative_paid > 0:
            status = "PARTIAL"
            is_paid = False
        else:
            status = "UNPAID"
            is_paid = False
        
        response_items.append(FeeStructureResponse(
            id=s.id,
            category=s.category,
            division=s.division,
            standard=s.standard,
            stream=s.stream,
            term=s.term,
            amount=s.amount,
            due_date=s.due_date,
            academic_year=s.academic_year,
            is_paid=is_paid,
            paid_amount=cumulative_paid,
            remaining_due=remaining_due,
            status=status,
            paid_date=paid_info["paid_date"] if paid_info else None,
            receipt_no=paid_info["receipt_no"] if paid_info else None,
            payment_id=paid_info["payment_id"] if paid_info else None
        ))

    return response_items

def get_all_fee_structures(db: Session, division: Optional[str] = None):
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
        academic_year=fee_in.academic_year
    )
    db.add(structure)
    db.commit()
    db.refresh(structure)
    return structure

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

def process_fee_collection(db: Session, collect_in: FeeCollectCreate) -> FeePayment:
    student = db.query(Student).filter(Student.id == collect_in.student_id).first()
    if not student:
        raise ValueError("Student not found")

    receipt_no = generate_receipt_number(db, student.academic_year)
    items_total = sum(item.amount for item in collect_in.items)
    
    # Check advance credit usage
    advance_used = min(student.advance_balance or 0.0, collect_in.advance_used or 0.0)
    if advance_used > 0:
        student.advance_balance -= advance_used
        
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
        collected_by=collect_in.collected_by
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
            remaining_due=max(0.0, (item.remaining_due or item.amount) - item.amount)
        )
        db.add(detail)

    # Recalculate remaining student balance
    structures = get_fee_structures_for_student(db, student.id)
    total_remaining_due = sum(st.remaining_due for st in structures)
    payment.pending_due = total_remaining_due
    
    db.commit()
    db.refresh(payment)
    db.refresh(student)
    return payment

def get_receipt_by_id(db: Session, receipt_id: int):
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
            "remaining_due": d.remaining_due or 0.0
        }
        for d in details
    ]
    
    # Fetch previous payment receipts for this student
    past_payments = db.query(FeePayment).filter(
        FeePayment.student_id == payment.student_id,
        FeePayment.id != payment.id,
        FeePayment.id < payment.id
    ).order_by(FeePayment.id.asc()).all()

    previous_payments_summary = []
    for past_p in past_payments:
        past_details = db.query(PaymentDetail).filter(PaymentDetail.payment_id == past_p.id).all()
        summary_str = ", ".join([f"{d.fee_head} (₹{d.amount:,.0f})" for d in past_details])
        previous_payments_summary.append({
            "id": past_p.id,
            "receipt_no": past_p.receipt_no,
            "payment_date": past_p.payment_date,
            "payment_mode": past_p.payment_mode,
            "net_paid": past_p.net_paid,
            "items_summary": summary_str
        })

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
        items=items,
        previous_payments=previous_payments_summary,
        total_amount=payment.total_amount,
        late_fine=payment.late_fine,
        discount=payment.discount,
        advance_used=payment.advance_used or 0.0,
        advance_balance_remaining=student.advance_balance if student else 0.0,
        net_paid=payment.net_paid,
        pending_due=payment.pending_due,
        collected_by=payment.collected_by
    )

def get_defaulter_list(db: Session, division: Optional[str] = None, standard: Optional[str] = None, min_due: float = 1.0):
    query = db.query(Student).filter(Student.status == "Active")
    if division and division != "All":
        query = query.filter(Student.division == division)
    if standard and standard != "All":
        query = query.filter(Student.standard == standard)
        
    students = query.all()
    defaulters = []
    
    for s in students:
        payments = db.query(FeePayment).filter(FeePayment.student_id == s.id).all()
        total_paid = sum(p.net_paid for p in payments)
        
        # Calculate total fee structure due for this student
        structures = get_fee_structures_for_student(db, s.id)
        total_due = sum(st.amount for st in structures)
        
        pending = max(0.0, total_due - total_paid)
        
        if pending >= min_due or not payments:
            defaulters.append(DefaulterResponse(
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
                pending_balance=pending if total_due > 0 else (23000.0 - total_paid)
            ))
            
    return defaulters

get_defaulters_list = get_defaulter_list

def get_all_payments_history(db: Session, academic_year: Optional[str] = "2026-2027", payment_mode: Optional[str] = None):
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
