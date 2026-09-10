from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union, Iterable

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.core.tenancy import set_current_tenant_id
from app.models.tenant import Tenant, TenantStatus
from app.models.user import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ROLE_SUPER_ADMIN = UserRole.SUPER_ADMIN.value
ROLE_SCHOOL_ADMIN = UserRole.SCHOOL_ADMIN.value
ROLE_TEACHER = UserRole.TEACHER.value
ROLE_STUDENT = UserRole.STUDENT.value

ADMIN_ROLES = (ROLE_SUPER_ADMIN, ROLE_SCHOOL_ADMIN, "admin")
STAFF_ROLES = (ROLE_SUPER_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER, "admin")
ALL_ROLES = STAFF_ROLES + (ROLE_STUDENT,)


class TokenPayload(BaseModel):
    sub: str                              # login identifier (email / GR no)
    role: str
    uid: Optional[int] = None             # primary key in users / teachers / students
    email: Optional[str] = None
    tenant_id: Optional[str] = None       # None only for SUPER_ADMIN
    tenant_slug: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None

    @property
    def is_super_admin(self) -> bool:
        return self.role == ROLE_SUPER_ADMIN


import bcrypt

# ────────── Passwords ──────────

def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except Exception:
        pass
    try:
        pw_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def is_password_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        if pwd_context.identify(value) is not None:
            return True
    except Exception:
        pass
    return value.startswith("$2b$") or value.startswith("$2a$") or value.startswith("$2y$")


# ────────── JWT ──────────

def create_access_token(
    subject: Union[str, Any],
    role: str,
    tenant_id: Optional[str] = None,
    tenant_slug: Optional[str] = None,
    email: Optional[str] = None,
    uid: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if role != ROLE_SUPER_ADMIN and not tenant_id:
        raise ValueError("Non-super-admin tokens must carry a tenant_id")

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "sub": str(subject),
        "role": role,
        "uid": uid,
        "email": email,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_token(token: Optional[str] = Depends(oauth2_scheme)) -> TokenPayload:
    """Strict authentication. There is intentionally no anonymous fallback."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(token)


# ────────── Tenant resolution ──────────

def requested_tenant_identifier(request: Request) -> Optional[str]:
    """
    A *hint* about which tenant the client wants to act on. Only honoured for
    Super Admins (who may switch schools) or when it matches the caller's own token.
    Sources, in order: X-Tenant-ID header, then <slug>.<TENANT_ROOT_DOMAIN> subdomain.
    """
    header = request.headers.get("X-Tenant-ID")
    if header and header.strip():
        return header.strip()

    root = settings.TENANT_ROOT_DOMAIN.lower().strip(".")
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if root and host.endswith("." + root):
        slug = host[: -(len(root) + 1)]
        if slug and "." not in slug and slug not in ("www", "api", "app"):
            return slug
    return None


def _load_tenant(db: Session, identifier: str) -> Optional[Tenant]:
    return (
        db.query(Tenant)
        .filter((Tenant.id == identifier) | (Tenant.slug == identifier.lower()))
        .first()
    )


def assert_tenant_usable(tenant: Optional[Tenant]) -> Tenant:
    if tenant is None:
        raise HTTPException(status_code=404, detail="School not found")
    if tenant.status != TenantStatus.VERIFIED:
        raise HTTPException(
            status_code=403,
            detail=f"School account is {tenant.status.value}. Contact platform support.",
        )
    if tenant.is_subscription_expired:
        raise HTTPException(status_code=403, detail="School subscription has expired. Please renew.")
    return tenant


def _resolve_tenant_sync(db: Session, token: TokenPayload, requested: Optional[str]) -> Tenant:
    if token.is_super_admin:
        if not requested:
            raise HTTPException(
                status_code=400,
                detail="Super Admin must specify the school to act on via the X-Tenant-ID header",
            )
        tenant = _load_tenant(db, requested)
        if tenant is None:
            raise HTTPException(status_code=404, detail="School not found")
        return tenant  # platform operators may inspect suspended / pending schools

    if not token.tenant_id:
        raise HTTPException(status_code=403, detail="User does not belong to any school")

    tenant = _load_tenant(db, token.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=403, detail="School for this session no longer exists")

    # A client may echo its own tenant back; anything else is tampering.
    if requested and requested not in (tenant.id, tenant.slug):
        raise HTTPException(status_code=403, detail="Tenant header does not match the authenticated session")

    return assert_tenant_usable(tenant)


async def TenantAuthGuard(
    request: Request,
    token: TokenPayload = Depends(get_current_user_token),
    db: Session = Depends(get_db),
) -> TokenPayload:
    """
    Authenticates the caller and activates the tenant context for this request.

    Runs as an *async* dependency on purpose: the contextvar must be set in the
    request task's context so it propagates into the thread that runs the sync
    endpoint (and into every SQLAlchemy query it makes).
    """
    requested = requested_tenant_identifier(request)
    tenant = await run_in_threadpool(_resolve_tenant_sync, db, token, requested)

    set_current_tenant_id(tenant.id)
    request.state.tenant_id = tenant.id
    request.state.tenant = tenant
    request.state.user = token
    return token


# ────────── Role guards ──────────

def SuperAdminGuard(token: TokenPayload = Depends(get_current_user_token)) -> TokenPayload:
    """Platform-level access. Does NOT activate a tenant context."""
    if token.role != ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Super Admin privileges required.",
        )
    return token


def require_roles(*roles: str):
    """Dependency factory: tenant-authenticated AND role in `roles`."""
    allowed = tuple(roles)

    async def _guard(token: TokenPayload = Depends(TenantAuthGuard)) -> TokenPayload:
        if token.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of: {', '.join(allowed)}",
            )
        return token

    return _guard


AdminGuard = require_roles(*ADMIN_ROLES)   # school admin or platform admin acting on a school
StaffGuard = require_roles(*STAFF_ROLES)   # admins + teachers
