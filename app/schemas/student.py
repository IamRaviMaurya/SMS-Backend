from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class StudentBase(BaseModel):
    # Name Breakdown (4a - 4d)
    last_name: str = Field(..., example="Patel")
    first_name: str = Field(..., example="Aarav")
    middle_name: Optional[str] = Field(None, example="Aniket")
    mother_name: str = Field(..., example="Sunita")
    
    # Address & Contact (5 & 6)
    address: str = Field(..., example="B-402, Gokul Heights, MG Road")
    pin_code: str = Field(..., example="400001")
    phone: str = Field(..., example="9820123456")
    email: Optional[str] = Field(None, example="parent@example.com")

    # Birth & Govt Identity (7 - 9)
    place_of_birth: str = Field(..., example="Mumbai")
    dob: str = Field(..., example="2014-05-15")
    aadhar_no: str = Field(..., example="1234-5678-9012")

    # Classifications (10 - 12)
    gender: str = Field(..., example="Male")
    religion: str = Field("Non-Minority", example="Non-Minority")
    category: str = Field("OPEN", example="OPEN")

    # Document Attachments (Optional)
    photo_url: Optional[str] = None
    signature_url: Optional[str] = None
    aadhar_front_url: Optional[str] = None
    aadhar_back_url: Optional[str] = None

    # Academic Division Setup
    division: str = Field(..., example="School Section")
    standard: str = Field(..., example="7th")
    section: str = Field("A", example="A")
    stream: Optional[str] = Field(None, example="Science")
    academic_year: str = Field("2026-2027", example="2026-2027")
    advance_balance: Optional[float] = Field(0.0, example=0.0)

class StudentCreate(StudentBase):
    gr_no: Optional[str] = None

class StudentUpdate(BaseModel):
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    mother_name: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    place_of_birth: Optional[str] = None
    dob: Optional[str] = None
    aadhar_no: Optional[str] = None
    gender: Optional[str] = None
    religion: Optional[str] = None
    category: Optional[str] = None
    photo_url: Optional[str] = None
    signature_url: Optional[str] = None
    aadhar_front_url: Optional[str] = None
    aadhar_back_url: Optional[str] = None
    division: Optional[str] = None
    standard: Optional[str] = None
    section: Optional[str] = None
    stream: Optional[str] = None
    status: Optional[str] = None
    advance_balance: Optional[float] = None

class StudentResponse(StudentBase):
    id: int
    gr_no: str
    full_name: str
    parent_name: Optional[str] = None
    advance_balance: float = 0.0
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

from app.schemas.fee import FeeStructureResponse, FeeReceiptResponse

class StudentFullLedgerResponse(BaseModel):
    student: StudentResponse
    structures: List[FeeStructureResponse]
    payment_history: List[FeeReceiptResponse]
    total_due: float
    total_paid: float
    advance_balance: float
    pending_balance: float

    class Config:
        from_attributes = True

StudentFullLedgerResponse.model_rebuild()
