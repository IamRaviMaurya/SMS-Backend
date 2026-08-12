from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
import jwt
from app.schemas.auth import LoginRequest, Token
from app.core.security import create_access_token
from app.core.database import get_db
from app.core.config import settings
from app.models.academic import Teacher
from app.models.student import Student

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    uname = credentials.username.strip()
    pwd = credentials.password.strip()

    # 1. Admin Login
    if uname.lower() in ["admin", "principal"] and pwd == "admin123":
        access_token = create_access_token(subject=uname)
        return Token(
            access_token=access_token,
            token_type="bearer",
            user_role="admin",
            full_name="Principal / Accounts Administrator"
        )
    
    # 2. Teacher Login
    teacher = db.query(Teacher).filter(Teacher.email.ilike(uname)).first()
    if teacher and (teacher.password == pwd or pwd == "teacher123"):
        access_token = create_access_token(subject=teacher.email)
        return Token(
            access_token=access_token,
            token_type="bearer",
            user_role="teacher",
            full_name=teacher.name,
            assigned_class=teacher.assigned_class,
            assigned_section=teacher.assigned_section,
            teacher_id=teacher.id
        )

    # 3. Student / Parent Login (Student Name as User ID, GR No as Password)
    student = db.query(Student).filter(
        (func.lower(Student.full_name) == uname.lower()) |
        (func.lower(Student.first_name) == uname.lower()) |
        (func.lower(Student.gr_no) == uname.lower()) |
        (Student.phone == uname) |
        (func.lower(Student.email) == uname.lower())
    ).first()

    if not student and uname.lower() in ["student", "parent"]:
        student = db.query(Student).filter(Student.status == "Active").first()

    if student:
        valid_pwds = [
            "student123", "parent123", "123456",
            student.gr_no.lower() if student.gr_no else "",
            student.first_name.lower() if student.first_name else "",
            student.full_name.lower() if student.full_name else "",
            student.dob if student.dob else "",
            student.phone if student.phone else ""
        ]
        if pwd.lower() in valid_pwds:
            access_token = create_access_token(subject=student.gr_no)
            return Token(
                access_token=access_token,
                token_type="bearer",
                user_role="student",
                full_name=student.full_name,
                assigned_class=student.standard,
                assigned_section=student.section,
                student_id=student.id,
                gr_no=student.gr_no,
                division=student.division
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Logins: Admin (admin/admin123), Teacher (verma@school.com/teacher123), Student (Student Name / GR No as password)."
    )

@router.get("/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token sub missing")
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate token")

    if username == "admin":
        return {
            "username": "admin",
            "role": "admin",
            "full_name": "Principal / Accounts Administrator",
            "school_name": "Avdhoot Bhagwan Ram Vidyalaya",
            "affiliation_no": "SSET/ABRV/2026"
        }
    
    # Check if teacher email matches
    teacher = db.query(Teacher).filter(Teacher.email == username).first()
    if teacher:
        return {
            "username": teacher.email,
            "role": "teacher",
            "full_name": teacher.name,
            "assigned_class": teacher.assigned_class,
            "assigned_section": teacher.assigned_section,
            "school_name": "Avdhoot Bhagwan Ram Vidyalaya",
            "affiliation_no": "SSET/ABRV/2026"
        }
    
    # Check if student GR No matches
    student = db.query(Student).filter(Student.gr_no == username).first()
    if student:
        return {
            "username": student.gr_no,
            "role": "student",
            "full_name": student.full_name,
            "assigned_class": student.standard,
            "assigned_section": student.section,
            "student_id": student.id,
            "gr_no": student.gr_no,
            "school_name": "Avdhoot Bhagwan Ram Vidyalaya",
            "affiliation_no": "SSET/ABRV/2026"
        }
    
    raise HTTPException(status_code=401, detail="User not found")
