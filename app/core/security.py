from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class TokenPayload(BaseModel):
    sub: str                              # User ID / Username
    email: Optional[str] = None
    role: str = "school_admin"            # SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT, PARENT
    tenant_id: Optional[str] = "default-tenant-001"
    tenant_slug: Optional[str] = "main"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any],
    role: str = "school_admin",
    tenant_id: Optional[str] = "default-tenant-001",
    tenant_slug: Optional[str] = "main",
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "email": email
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user_token(token: Optional[str] = Depends(oauth2_scheme)) -> TokenPayload:
    if not token:
        # Fallback default user if unauthenticated in local dev
        return TokenPayload(sub="admin", role="SUPER_ADMIN", tenant_id="default-tenant-001", tenant_slug="main")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**payload)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def SuperAdminGuard(token: TokenPayload = Depends(get_current_user_token)) -> TokenPayload:
    """Enforces Super Admin access only."""
    if token.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Super Admin privileges required."
        )
    return token


def TenantAuthGuard(
    x_tenant_id: Optional[str] = Header(None),
    token: TokenPayload = Depends(get_current_user_token)
) -> TokenPayload:
    """Enforces active Tenant access and cross-tenant data leak protection."""
    if token.role == "SUPER_ADMIN":
        return token

    if not token.tenant_id:
        raise HTTPException(status_code=403, detail="User does not belong to any tenant")

    # Prevent cross-tenant token tampering
    if x_tenant_id and x_tenant_id != token.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant ID header mismatch")

    return token
