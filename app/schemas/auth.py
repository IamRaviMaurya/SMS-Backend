from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str
    # School slug or tenant id. Optional because it can also come from the
    # X-Tenant-ID header or a <slug>.<root-domain> host. Not needed for Super Admin.
    tenant: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # UI-facing role label kept for the existing web/mobile clients:
    # "SUPER_ADMIN" | "admin" | "teacher" | "student"
    user_role: str
    role: str                                 # canonical role stored in the JWT
    full_name: str
    tenant_id: Optional[str] = None
    tenant_slug: Optional[str] = None
    school_name: Optional[str] = None
    must_change_password: bool = False
    assigned_class: Optional[str] = None
    assigned_section: Optional[str] = None
    teacher_id: Optional[int] = None
    student_id: Optional[int] = None
    gr_no: Optional[str] = None
    division: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenData(BaseModel):
    username: Optional[str] = None
