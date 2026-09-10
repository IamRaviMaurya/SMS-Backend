from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    ROLE_SCHOOL_ADMIN, ROLE_STUDENT, ROLE_SUPER_ADMIN, ROLE_TEACHER,
    TokenPayload, assert_tenant_usable, create_access_token, get_current_user_token,
    get_password_hash, is_password_hash, requested_tenant_identifier, verify_password,
)
from app.core.tenancy import tenant_scope
from app.models.academic import Teacher
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["Authentication"])

_INVALID = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _ui_role(role: str) -> str:
    """Role label the existing Next.js / Flutter clients switch on."""
    return {
        ROLE_SUPER_ADMIN: "SUPER_ADMIN",
        ROLE_SCHOOL_ADMIN: "admin",
        ROLE_TEACHER: "teacher",
        ROLE_STUDENT: "student",
    }[role]


def _find_tenant(db: Session, identifier: Optional[str]) -> Optional[Tenant]:
    if not identifier:
        return None
    return (
        db.query(Tenant)
        .filter((Tenant.id == identifier) | (Tenant.slug == identifier.lower()))
        .first()
    )


def _teacher_password_ok(db: Session, teacher: Teacher, password: str) -> bool:
    """
    Verifies a teacher password. Rows migrated from the old plaintext column are
    upgraded to bcrypt on their first successful login.
    """
    stored = teacher.password_hash
    if not stored:
        return False
    if is_password_hash(stored):
        return verify_password(password, stored)
    if stored == password:  # legacy plaintext, upgrade in place
        teacher.password_hash = get_password_hash(password)
        db.commit()
        return True
    return False


@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    uname = credentials.username.strip()
    pwd = credentials.password
    if not uname or not pwd:
        raise _INVALID

    # ── 1. Platform Super Admin (no tenant) ──
    platform_user = (
        db.query(User)
        .filter(
            func.lower(User.email) == uname.lower(),
            User.role == ROLE_SUPER_ADMIN,
            User.tenant_id.is_(None),
        )
        .first()
    )
    if platform_user:
        if not platform_user.is_active or not verify_password(pwd, platform_user.password_hash):
            raise _INVALID
        platform_user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        return Token(
            access_token=create_access_token(
                subject=platform_user.email, role=ROLE_SUPER_ADMIN,
                email=platform_user.email, uid=platform_user.id,
            ),
            user_role="SUPER_ADMIN",
            role=ROLE_SUPER_ADMIN,
            full_name=platform_user.full_name,
            must_change_password=platform_user.must_change_password,
        )

    # ── 2. Everyone else belongs to exactly one school ──
    tenant = _find_tenant(db, credentials.tenant) or _find_tenant(db, requested_tenant_identifier(request))
    if tenant is None:
        raise HTTPException(
            status_code=400,
            detail="School not specified. Log in from your school's login page (or send X-Tenant-ID).",
        )
    assert_tenant_usable(tenant)

    with tenant_scope(tenant.id):
        # 2a. School Admin
        school_admin = (
            db.query(User)
            .filter(
                User.tenant_id == tenant.id,
                func.lower(User.email) == uname.lower(),
                User.role == ROLE_SCHOOL_ADMIN,
            )
            .first()
        )
        if school_admin:
            if not school_admin.is_active or not verify_password(pwd, school_admin.password_hash):
                raise _INVALID
            school_admin.last_login_at = datetime.now(timezone.utc)
            db.commit()
            return Token(
                access_token=create_access_token(
                    subject=school_admin.email, role=ROLE_SCHOOL_ADMIN,
                    tenant_id=tenant.id, tenant_slug=tenant.slug,
                    email=school_admin.email, uid=school_admin.id,
                ),
                user_role="admin",
                role=ROLE_SCHOOL_ADMIN,
                full_name=school_admin.full_name,
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                school_name=tenant.school_name,
                must_change_password=school_admin.must_change_password,
            )

        # 2b. Teacher (tenant filter applied automatically by the scoping hook)
        teacher = db.query(Teacher).filter(func.lower(Teacher.email) == uname.lower()).first()
        if teacher:
            if teacher.status != "Active" or not _teacher_password_ok(db, teacher, pwd):
                raise _INVALID
            return Token(
                access_token=create_access_token(
                    subject=teacher.email, role=ROLE_TEACHER,
                    tenant_id=tenant.id, tenant_slug=tenant.slug,
                    email=teacher.email, uid=teacher.id,
                ),
                user_role="teacher",
                role=ROLE_TEACHER,
                full_name=teacher.name,
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                school_name=tenant.school_name,
                assigned_class=teacher.assigned_class,
                assigned_section=teacher.assigned_section,
                teacher_id=teacher.id,
            )

        # 2c. Student / Parent: username = GR No / phone / email, password = DOB (YYYY-MM-DD) or phone
        student = (
            db.query(Student)
            .filter(
                Student.status == "Active",
                or_(
                    func.lower(Student.gr_no) == uname.lower(),
                    Student.phone == uname,
                    func.lower(Student.email) == uname.lower(),
                ),
            )
            .first()
        )
        if student:
            accepted = {v for v in (student.dob, student.phone) if v}
            if pwd not in accepted:
                raise _INVALID
            return Token(
                access_token=create_access_token(
                    subject=student.gr_no, role=ROLE_STUDENT,
                    tenant_id=tenant.id, tenant_slug=tenant.slug,
                    email=student.email, uid=student.id,
                ),
                user_role="student",
                role=ROLE_STUDENT,
                full_name=student.full_name,
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                school_name=tenant.school_name,
                assigned_class=student.standard,
                assigned_section=student.section,
                student_id=student.id,
                gr_no=student.gr_no,
                division=student.division,
            )

    raise _INVALID


@router.get("/me")
def get_current_user(token: TokenPayload = Depends(get_current_user_token), db: Session = Depends(get_db)):
    if token.is_super_admin:
        return {
            "username": token.sub,
            "role": "SUPER_ADMIN",
            "full_name": "Platform Super Admin",
            "school_name": settings.PROJECT_NAME,
            "tenant_id": None,
        }

    tenant = _find_tenant(db, token.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=401, detail="School for this session no longer exists")

    base = {
        "username": token.sub,
        "role": _ui_role(token.role),
        "tenant_id": tenant.id,
        "tenant_slug": tenant.slug,
        "school_name": tenant.school_name,
    }

    with tenant_scope(tenant.id):
        if token.role == ROLE_SCHOOL_ADMIN:
            user = db.query(User).filter(User.id == token.uid, User.tenant_id == tenant.id).first()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return {**base, "full_name": user.full_name}

        if token.role == ROLE_TEACHER:
            teacher = db.query(Teacher).filter(Teacher.id == token.uid).first()
            if not teacher:
                raise HTTPException(status_code=401, detail="User not found")
            return {
                **base,
                "full_name": teacher.name,
                "assigned_class": teacher.assigned_class,
                "assigned_section": teacher.assigned_section,
                "teacher_id": teacher.id,
            }

        student = db.query(Student).filter(Student.id == token.uid).first()
        if not student:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            **base,
            "full_name": student.full_name,
            "assigned_class": student.standard,
            "assigned_section": student.section,
            "student_id": student.id,
            "gr_no": student.gr_no,
        }


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    token: TokenPayload = Depends(get_current_user_token),
    db: Session = Depends(get_db),
):
    if token.role in (ROLE_SUPER_ADMIN, ROLE_SCHOOL_ADMIN):
        user = db.query(User).filter(User.id == token.uid).first()
        if not user or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash = get_password_hash(body.new_password)
        user.must_change_password = False
        db.commit()
        return {"message": "Password updated"}

    if token.role == ROLE_TEACHER:
        with tenant_scope(token.tenant_id):
            teacher = db.query(Teacher).filter(Teacher.id == token.uid).first()
            if not teacher or not _teacher_password_ok(db, teacher, body.current_password):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            teacher.password_hash = get_password_hash(body.new_password)
            db.commit()
        return {"message": "Password updated"}

    raise HTTPException(status_code=403, detail="Students cannot change their password here")
