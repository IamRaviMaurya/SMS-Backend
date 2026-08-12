from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate, StudentFullLedgerResponse
from app.services import student_service

router = APIRouter(prefix="/students", tags=["Students"])

@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def register_student(student_in: StudentCreate, db: Session = Depends(get_db)):
    """
    Multi-step Admission Form Endpoint.
    Auto-generates GR Number if omitted.
    Assigns division, standard, section & stream (Science, Commerce, Arts for Junior College).
    """
    return student_service.create_student(db, student_in)

@router.get("/next-gr")
def get_next_gr_number(academic_year: str = "2026-2027", db: Session = Depends(get_db)):
    next_gr = student_service.generate_gr_number(db, academic_year)
    return {"next_gr_no": next_gr}

@router.get("/count-breakdown")
def get_student_count_breakdown_endpoint(academic_year: Optional[str] = Query("2026-2027"), db: Session = Depends(get_db)):
    return student_service.get_student_count_breakdown(db, academic_year)

@router.get("/stats")
def get_students_stats(db: Session = Depends(get_db)):
    from app.models.student import Student
    total = db.query(Student).count()
    active = db.query(Student).filter(Student.status == "Active").count()
    return {
        "total_students": total,
        "active_students": active
    }

@router.get("", response_model=List[StudentResponse])
def list_students(
    response: Response,
    search: Optional[str] = Query(None, description="Search by GR No, Full Name, Parent Name, or Phone"),
    division: Optional[str] = Query(None, description="Filter by Division (Pre-Primary, School Section, Junior College)"),
    standard: Optional[str] = Query(None, description="Filter by Standard (Nursery, 1st - 12th)"),
    section: Optional[str] = Query(None, description="Filter by Section (A, B, C)"),
    stream: Optional[str] = Query(None, description="Filter by Stream (Science, Commerce, Arts)"),
    student_status: Optional[str] = Query(None, alias="status", description="Filter by Status (Active, Passed, Left)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(100, ge=1, description="Number of items per page"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * limit
    total = student_service.count_students(
        db,
        search=search,
        division=division,
        standard=standard,
        section=section,
        stream=stream,
        status=student_status
    )
    students = student_service.get_students(
        db, 
        search=search, 
        division=division, 
        standard=standard, 
        section=section,
        stream=stream, 
        status=student_status,
        skip=skip, 
        limit=limit
    )
    
    # Expose custom pagination header
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return students

@router.get("/{identifier}/full-ledger", response_model=StudentFullLedgerResponse)
def get_student_ledger_endpoint(identifier: str, db: Session = Depends(get_db)):
    ledger_data = student_service.get_student_full_ledger(db, identifier)
    if not ledger_data:
        raise HTTPException(status_code=404, detail="Student record not found")
    return ledger_data

@router.get("/{identifier}", response_model=StudentResponse)
def get_student(identifier: str, db: Session = Depends(get_db)):
    # Check if integer ID or string GR No
    if identifier.isdigit():
        student = student_service.get_student_by_id(db, int(identifier))
    else:
        student = student_service.get_student_by_gr(db, identifier)
        
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.put("/{student_id}", response_model=StudentResponse)
def update_student_record(student_id: int, student_in: StudentUpdate, db: Session = Depends(get_db)):
    updated_student = student_service.update_student(db, student_id, student_in)
    if not updated_student:
        raise HTTPException(status_code=404, detail="Student record not found")
    return updated_student
