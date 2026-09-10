import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import SuperAdminGuard, TokenPayload
from app.models.tenant import Tenant, TenantStatus, SubscriptionPlan
from app.models.student import Student

router = APIRouter(prefix="/super-admin", tags=["Super Admin Platform Management"])


# ────────── SCHEMAS ──────────
class SchoolRegistrationRequest(BaseModel):
    school_name: str
    slug: str
    contact_email: EmailStr
    contact_phone: str
    address: Optional[str] = None
    subscription_plan: SubscriptionPlan = SubscriptionPlan.FREE_TRIAL


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


# ────────── PUBLIC SCHOOL SELF-REGISTRATION ──────────
@router.post("/register-school", status_code=status.HTTP_201_CREATED)
def register_new_school(req: SchoolRegistrationRequest, db: Session = Depends(get_db)):
    """Public endpoint for new schools to register for SaaS onboarding."""
    existing = db.query(Tenant).filter(Tenant.slug == req.slug.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="School URL slug already taken")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        school_name=req.school_name,
        slug=req.slug.lower(),
        contact_email=req.contact_email,
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
    On VERIFIED: Sets subscription expiration date and generates initial School Admin credentials.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant school not found")

    tenant.status = action.status
    credentials = None

    if action.status == TenantStatus.VERIFIED:
        tenant.student_limit = action.student_limit or 500
        tenant.subscription_expires_at = datetime.utcnow() + timedelta(days=action.subscription_days or 365)

        credentials = {
            "school_id": tenant.id,
            "school_slug": tenant.slug,
            "admin_email": tenant.contact_email,
            "temporary_password": f"Admin@{tenant.slug.capitalize()}2026!",
            "login_url": f"https://{tenant.slug}.sms.com/login",
        }

    db.commit()
    db.refresh(tenant)

    return {
        "message": f"Tenant school status updated to {action.status}",
        "tenant_id": tenant.id,
        "status": tenant.status,
        "student_limit": tenant.student_limit,
        "subscription_expires_at": tenant.subscription_expires_at,
        "credentials": credentials,
    }


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
    total_students_platform = db.query(Student).count()

    # Estimate Monthly Recurring Revenue (MRR)
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
    }
