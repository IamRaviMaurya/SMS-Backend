import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"      # Platform operator, tenant_id is NULL
    SCHOOL_ADMIN = "SCHOOL_ADMIN"    # Principal / accounts admin of one tenant
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class User(Base):
    """
    Login accounts for platform Super Admins and per-school Admins.
    Teachers and Students authenticate against their own tables.

    NOTE: deliberately NOT a TenantMixin. Super Admin rows have tenant_id = NULL and
    the login flow must be able to look users up before a tenant context exists.
    Every query on this table must therefore filter tenant_id explicitly.
    """
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="ux_users_tenant_email"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.SCHOOL_ADMIN.value)
    full_name = Column(String(100), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
