from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_role: str = "admin"
    full_name: str = "Administrator"
    assigned_class: Optional[str] = None
    assigned_section: Optional[str] = None
    teacher_id: Optional[int] = None
    student_id: Optional[int] = None
    gr_no: Optional[str] = None
    division: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None
