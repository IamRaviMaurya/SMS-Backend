import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ROLE_SCHOOL_ADMIN, SuperAdminGuard, TokenPayload, get_password_hash
from app.core.tenancy import bypass_tenant_scope
from app.models.student import Student
from app.models.tenant import SubscriptionPlan, Tenant, TenantStatus
from app.models.user import User

router = APIRouter(prefix="/super-admin", tags=["Super Admin Platform Management"])

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$")
_RESERVED_SLUGS = {"www", "api", "app", "admin", "platform", "superadmin", "login", "static"}


# ────────── SCHEMAS ──────────
class SchoolRegistrationRequest(BaseModel):
    school_name: str
    slug: str
    contact_email: EmailStr
    contact_phone: str
    address: Optional[str] = None
    subscription_plan: SubscriptionPlan = SubscriptionPlan.FREE_TRIAL

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v) or v in _RESERVED_SLUGS:
            raise ValueError("Slug must be 3-50 chars, lowercase letters/digits/hyphens, and not reserved")
        return v


class SchoolVerificationAction(BaseModel):
    status: TenantStatus
    student_limit: Optional[int] = 500
    subscription_days: Optional[int] = 365
    admin_notes: Optional[str] = None


class TenantResponse(BaseModel):
    id: str
    school_name: str
    slug: str
    domain: Optional[str] = None
    contact_email: str
    contact_phone: str
    address: Optional[str] = None
    status: TenantStatus
    subscription_plan: SubscriptionPlan
    student_limit: int
    subscription_expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ────────── HELPERS ──────────
def _get_tenant_or_404(db: Session, tenant_id: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant school not found")
    return tenant


def _upsert_school_admin(db: Session, tenant: Tenant, temp_password: str) -> User:
    """Create (or reset) the school's primary admin login. Password is returned to the caller once."""
    admin = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.role == ROLE_SCHOOL_ADMIN)
        .order_by(User.id.asc())
        .first()
    )
    if admin is None:
        admin = User(
            email=tenant.contact_email.lower(),
            role=ROLE_SCHOOL_ADMIN,
            full_name=f"{tenant.school_name} Administrator",
            tenant_id=tenant.id,
        )
        db.add(admin)
    admin.password_hash = get_password_hash(temp_password)
    admin.is_active = True
    admin.must_change_password = True
    return admin


def _credentials_payload(tenant: Tenant, admin: User, temp_password: str) -> dict:
    return {
        "school_id": tenant.id,
        "school_slug": tenant.slug,
        "admin_email": admin.email,
        "temporary_password": temp_password,
        "login_path": f"/{tenant.slug}/login",
    }


# ────────── PUBLIC TENANT BRANDING INFO ──────────
@router.get("/tenant-info/{identifier}")
def get_tenant_public_info(identifier: str, db: Session = Depends(get_db)):
    """Public endpoint to fetch tenant school branding info (name, logo, colors) for dynamic login screen."""
    if identifier.lower() in ["platform", "superadmin", "admin"]:
        return {
            "id": "platform",
            "school_name": "SaaS Platform Control Console",
            "slug": "platform",
            "logo_url": None,
            "primary_color": "#3B82F6",
            "secondary_color": "#1E3A8A",
            "status": "VERIFIED",
        }

    tenant = (
        db.query(Tenant)
        .filter((Tenant.slug == identifier.lower()) | (Tenant.id == identifier))
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="School not found")

    return {
        "id": tenant.id,
        "school_name": tenant.school_name,
        "slug": tenant.slug,
        "logo_url": tenant.logo_url,
        "primary_color": tenant.primary_color or "#10B981",
        "secondary_color": tenant.secondary_color or "#072654",
        "status": tenant.status,
    }


# ────────── PUBLIC SCHOOL SELF-REGISTRATION ──────────
@router.post("/register-school", status_code=status.HTTP_201_CREATED)
def register_new_school(req: SchoolRegistrationRequest, db: Session = Depends(get_db)):
    """Public endpoint for new schools to register for SaaS onboarding."""
    existing = db.query(Tenant).filter(Tenant.slug == req.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="School URL slug already taken")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        school_name=req.school_name.strip(),
        slug=req.slug,
        contact_email=req.contact_email.lower(),
        contact_phone=req.contact_phone,
        address=req.address,
        status=TenantStatus.PENDING,
        subscription_plan=req.subscription_plan,
        student_limit=50 if req.subscription_plan == SubscriptionPlan.FREE_TRIAL else 500,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return {
        "message": "School registration submitted successfully. Pending Super Admin verification.",
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "status": tenant.status,
    }


# ────────── SUPER ADMIN VERIFICATION QUEUE ──────────
@router.get("/schools", response_model=List[TenantResponse])
def list_all_tenants(
    status_filter: Optional[TenantStatus] = Query(None),
    db: Session = Depends(get_db),
    admin: TokenPayload = Depends(SuperAdminGuard),
):
    """Super Admin queue listing all registered tenant schools."""
    query = db.query(Tenant)
    if status_filter:
        query = query.filter(Tenant.status == status_filter)
    return query.order_by(Tenant.created_at.desc()).all()


@router.patch("/schools/{tenant_id}/verify")
def verify_and_onboard_school(
    tenant_id: str,
    action: SchoolVerificationAction,
    db: Session = Depends(get_db),
    admin: TokenPayload = Depends(SuperAdminGuard),
):
    """
    Approve, Reject, or Suspend school access.
    On VERIFIED: sets subscription expiration and (first time only) creates the
    School Admin login with a one-time temporary password.
    """
    tenant = _get_tenant_or_404(db, tenant_id)
    previous_status = tenant.status
    tenant.status = action.status
    credentials = None

    if action.status == TenantStatus.VERIFIED:
        tenant.student_limit = action.student_limit or 500
        tenant.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=action.subscription_days or 365)

        has_admin = db.query(User).filter(User.tenant_id == tenant.id, User.role == ROLE_SCHOOL_ADMIN).first()
        if has_admin is None or previous_status != TenantStatus.VERIFIED:
            temp_password = secrets.token_urlsafe(9)
            school_admin = _upsert_school_admin(db, tenant, temp_password)
            db.flush()
            credentials = _credentials_payload(tenant, school_admin, temp_password)

    db.commit()
    db.refresh(tenant)

    return {
        "message": f"Tenant school status updated to {action.status.value}",
        "tenant_id": tenant.id,
        "status": tenant.status,
        "student_limit": tenant.student_limit,
        "subscription_expires_at": tenant.subscription_expires_at,
        "credentials": credentials,
    }


@router.post("/schools/{tenant_id}/reset-admin-password")
def reset_school_admin_password(
    tenant_id: str,
    db: Session = Depends(get_db),
    admin: TokenPayload = Depends(SuperAdminGuard),
):
    """Issue a fresh one-time password for a school's primary admin account."""
    tenant = _get_tenant_or_404(db, tenant_id)
    temp_password = secrets.token_urlsafe(9)
    school_admin = _upsert_school_admin(db, tenant, temp_password)
    db.commit()
    db.refresh(school_admin)
    return {"message": "School admin password reset", "credentials": _credentials_payload(tenant, school_admin, temp_password)}


# ────────── GLOBAL PLATFORM ANALYTICS ──────────
@router.get("/analytics")
def get_global_saas_metrics(
    db: Session = Depends(get_db),
    admin: TokenPayload = Depends(SuperAdminGuard),
):
    """Global SaaS Analytics: Schools count, active students platform-wide, and MRR metrics."""
    total_schools = db.query(Tenant).count()
    active_schools = db.query(Tenant).filter(Tenant.status == TenantStatus.VERIFIED).count()
    pending_verifications = db.query(Tenant).filter(Tenant.status == TenantStatus.PENDING).count()

    # Cross-tenant aggregate: explicit, audited opt-out of tenant scoping.
    with bypass_tenant_scope():
        total_students_platform = db.query(Student).count()
        student_rows = db.query(Student.created_at).all()

    # 6-month trend series (oldest -> newest) for dashboard sparklines.
    months = _last_months(6)
    school_rows = db.query(Tenant.created_at, Tenant.subscription_plan, Tenant.status).all()
    schools_trend = _cumulative_by_month(months, [r[0] for r in school_rows])
    students_trend = _cumulative_by_month(months, [r[0] for r in student_rows])
    mrr_trend = []
    for m in months:
        active = [r for r in school_rows if r[2] == TenantStatus.VERIFIED and r[0] and _ym(r[0]) <= m]
        mrr_trend.append(
            sum(2999.0 for r in active if r[1] == SubscriptionPlan.BASIC)
            + sum(7999.0 for r in active if r[1] == SubscriptionPlan.PREMIUM)
        )

    basic_plans = db.query(Tenant).filter(Tenant.subscription_plan == SubscriptionPlan.BASIC, Tenant.status == TenantStatus.VERIFIED).count()
    premium_plans = db.query(Tenant).filter(Tenant.subscription_plan == SubscriptionPlan.PREMIUM, Tenant.status == TenantStatus.VERIFIED).count()
    estimated_mrr = (basic_plans * 2999.0) + (premium_plans * 7999.0)

    return {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "pending_verifications": pending_verifications,
        "total_students_across_all_tenants": total_students_platform,
        "estimated_mrr_inr": estimated_mrr,
        "plans_breakdown": {
            "FREE_TRIAL": db.query(Tenant).filter(Tenant.subscription_plan == SubscriptionPlan.FREE_TRIAL).count(),
            "BASIC": basic_plans,
            "PREMIUM": premium_plans,
        },
        "trends": {
            "months": months,
            "schools": schools_trend,
            "students": students_trend,
            "mrr": mrr_trend,
            "new_students_last_month": _count_in_month(months[-1], [r[0] for r in student_rows]),
        },
    }


# ────────── trend helpers ──────────
def _ym(dt) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _last_months(n: int) -> List[str]:
    today = datetime.now(timezone.utc)
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _cumulative_by_month(months: List[str], stamps) -> List[int]:
    keys = [_ym(d) for d in stamps if d]
    undated = sum(1 for d in stamps if not d)
    return [undated + sum(1 for k in keys if k <= m) for m in months]


def _count_in_month(month: str, stamps) -> int:
    return sum(1 for d in stamps if d and _ym(d) == month)
