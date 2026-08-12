from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate

def generate_gr_number(db: Session, academic_year: str = "2026-2027") -> str:
    year = academic_year.split("-")[0]
    prefix = f"GR-{year}-"
    
    last_student = db.query(Student).filter(Student.gr_no.like(f"{prefix}%")).order_by(Student.id.desc()).first()
    if not last_student:
        return f"{prefix}0001"
    
    try:
        last_num = int(last_student.gr_no.split("-")[-1])
        new_num = last_num + 1
        return f"{prefix}{new_num:04d}"
    except ValueError:
        total_count = db.query(Student).count() + 1
        return f"{prefix}{total_count:04d}"

def create_student(db: Session, student_in: StudentCreate) -> Student:
    if not student_in.gr_no:
        student_in.gr_no = generate_gr_number(db, student_in.academic_year)
        
    full_name_parts = [student_in.first_name]
    if student_in.middle_name:
        full_name_parts.append(student_in.middle_name)
    full_name_parts.append(student_in.last_name)
    full_name = " ".join(full_name_parts)

    parent_name = f"{student_in.middle_name or student_in.first_name} {student_in.last_name}"

    student = Student(
        gr_no=student_in.gr_no,
        last_name=student_in.last_name,
        first_name=student_in.first_name,
        middle_name=student_in.middle_name,
        mother_name=student_in.mother_name,
        full_name=full_name,
        parent_name=parent_name,
        address=student_in.address,
        pin_code=student_in.pin_code,
        phone=student_in.phone,
        email=student_in.email,
        place_of_birth=student_in.place_of_birth,
        dob=student_in.dob,
        aadhar_no=student_in.aadhar_no,
        gender=student_in.gender,
        religion=student_in.religion,
        category=student_in.category,
        photo_url=student_in.photo_url,
        signature_url=student_in.signature_url,
        aadhar_front_url=student_in.aadhar_front_url,
        aadhar_back_url=student_in.aadhar_back_url,
        division=student_in.division,
        standard=student_in.standard,
        section=student_in.section,
        stream=student_in.stream,
        academic_year=student_in.academic_year,
        status="Active"
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

def count_students(
    db: Session,
    search: Optional[str] = None,
    division: Optional[str] = None,
    standard: Optional[str] = None,
    section: Optional[str] = None,
    stream: Optional[str] = None,
    status: Optional[str] = None
) -> int:
    query = db.query(Student)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Student.gr_no.ilike(term),
                Student.full_name.ilike(term),
                Student.aadhar_no.ilike(term),
                Student.phone.ilike(term),
                Student.last_name.ilike(term)
            )
        )
    if division and division != "All":
        query = query.filter(Student.division == division)
    if standard and standard != "All":
        query = query.filter(Student.standard == standard)
    if section and section != "All":
        query = query.filter(Student.section == section)
    if stream and stream != "All":
        query = query.filter(Student.stream == stream)
    if status and status != "All":
        query = query.filter(Student.status == status)
        
    return query.count()

def get_students(
    db: Session,
    search: Optional[str] = None,
    division: Optional[str] = None,
    standard: Optional[str] = None,
    section: Optional[str] = None,
    stream: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Student]:
    query = db.query(Student)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Student.gr_no.ilike(term),
                Student.full_name.ilike(term),
                Student.aadhar_no.ilike(term),
                Student.phone.ilike(term),
                Student.last_name.ilike(term)
            )
        )
    if division and division != "All":
        query = query.filter(Student.division == division)
    if standard and standard != "All":
        query = query.filter(Student.standard == standard)
    if section and section != "All":
        query = query.filter(Student.section == section)
    if stream and stream != "All":
        query = query.filter(Student.stream == stream)
    if status and status != "All":
        query = query.filter(Student.status == status)
        
    return query.order_by(Student.id.desc()).offset(skip).limit(limit).all()

def get_student_by_gr(db: Session, gr_no: str) -> Student:
    return db.query(Student).filter(Student.gr_no == gr_no).first()

def get_student_by_id(db: Session, student_id: int) -> Student:
    return db.query(Student).filter(Student.id == student_id).first()

def update_student(db: Session, student_id: int, student_in: StudentUpdate) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    update_data = student_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(student, field, value)

    # Re-compute full_name if name parts were provided
    if any(k in update_data for k in ["first_name", "middle_name", "last_name"]):
        full_name_parts = [student.first_name]
        if student.middle_name:
            full_name_parts.append(student.middle_name)
        full_name_parts.append(student.last_name)
        student.full_name = " ".join(full_name_parts)
        student.parent_name = f"{student.middle_name or student.first_name} {student.last_name}"

    db.commit()
    db.refresh(student)
    return student

def get_student_full_ledger(db: Session, identifier: str):
    if str(identifier).isdigit():
        student = get_student_by_id(db, int(identifier))
    else:
        student = get_student_by_gr(db, str(identifier))
        
    if not student:
        return None
        
    from app.services import fee_service
    from app.models.fee import FeePayment
    
    structures = fee_service.get_fee_structures_for_student(db, student.id)
    payments = db.query(FeePayment).filter(FeePayment.student_id == student.id).order_by(FeePayment.id.desc()).all()
    
    payment_history = []
    for p in payments:
        receipt = fee_service.get_receipt_by_id(db, p.id)
        if receipt:
            payment_history.append(receipt)
            
    total_due = sum(st.amount for st in structures)
    total_paid = sum(p.net_paid for p in payments)
    pending_balance = sum(st.remaining_due for st in structures)
    
    return {
        "student": student,
        "structures": structures,
        "payment_history": payment_history,
        "total_due": total_due,
        "total_paid": total_paid,
        "advance_balance": student.advance_balance or 0.0,
        "pending_balance": pending_balance
    }

def get_student_count_breakdown(db: Session, academic_year: Optional[str] = "2026-2027"):
    query = db.query(Student).filter(Student.status == "Active")
    if academic_year and academic_year != "All":
        query = query.filter(Student.academic_year == academic_year)
        
    total_students = query.count()
    
    # Division breakdown
    div_rows = query.with_entities(Student.division, func.count(Student.id)).group_by(Student.division).all()
    division_breakdown = [{"division": div, "count": cnt} for div, cnt in div_rows]
    
    # Standard breakdown
    std_rows = query.with_entities(Student.division, Student.standard, func.count(Student.id)).group_by(Student.division, Student.standard).all()
    standard_breakdown = [{"division": div, "standard": std, "count": cnt} for div, std, cnt in std_rows]
    
    # Section breakdown
    sec_rows = query.with_entities(Student.division, Student.standard, Student.section, func.count(Student.id)).group_by(Student.division, Student.standard, Student.section).all()
    section_breakdown = [{"division": div, "standard": std, "section": sec, "count": cnt} for div, std, sec, cnt in sec_rows]
    
    # Stream breakdown
    stream_rows = query.filter(Student.stream.isnot(None), Student.stream != "").with_entities(Student.standard, Student.stream, func.count(Student.id)).group_by(Student.standard, Student.stream).all()
    stream_breakdown = [{"standard": std, "stream": stm, "count": cnt} for std, stm, cnt in stream_rows]

    return {
        "academic_year": academic_year,
        "total_students": total_students,
        "division_breakdown": division_breakdown,
        "standard_breakdown": standard_breakdown,
        "section_breakdown": section_breakdown,
        "stream_breakdown": stream_breakdown
    }
