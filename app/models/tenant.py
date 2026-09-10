import enum
import uuid
from sqlalchemy import Column, String, DateTime, Enum, Integer, Text, ForeignKey
from sqlalchemy.orm import declared_attr
from sqlalchemy.sql import func
from datetime import datetime, timezone
from app.core.database import Base


class TenantStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


class SubscriptionPlan(str, enum.Enum):
    FREE_TRIAL = "FREE_TRIAL"
    BASIC = "BASIC"         # Limit: 500 Students
    PREMIUM = "PREMIUM"     # Unlimited Students


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    school_name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)   # e.g. "greenwood"
    domain = Column(String(255), unique=True, nullable=True)              # e.g. "greenwoodhigh.edu.in"
    
    # Custom Branding
    logo_url = Column(Text, nullable=True)
    primary_color = Column(String(20), default="#10B981")
    secondary_color = Column(String(20), default="#072654")

    # KYC & Contact
    contact_email = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=True)
    kyc_document_url = Column(Text, nullable=True)

    # Status & Subscription
    status = Column(Enum(TenantStatus), default=TenantStatus.PENDING, nullable=False)
    subscription_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE_TRIAL, nullable=False)
    student_limit = Column(Integer, default=100)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def is_subscription_expired(self) -> bool:
        if not self.subscription_expires_at:
            return False
        expires = self.subscription_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires < datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.VERIFIED and not self.is_subscription_expired


class TenantMixin:
    """Inherit this mixin on all tenant-isolated SQLAlchemy models."""
    @declared_attr
    def tenant_id(cls):
        return Column(
            String(50),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
