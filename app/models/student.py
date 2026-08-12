from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    gr_no = Column(String(50), unique=True, index=True, nullable=False)
    
    # 4a - 4d Name breakdown
    last_name = Column(String(100), nullable=False)      # 4a Last Name / Surname
    first_name = Column(String(100), nullable=False)     # 4b Candidate's First Name
    middle_name = Column(String(100), nullable=True)     # 4c Middle / Father's Name
    mother_name = Column(String(100), nullable=False)    # 4d Mother's Name
    full_name = Column(String(255), nullable=False, index=True) # Full Name combination

    # 5 Address & Contact
    address = Column(String(255), nullable=False)        # 5 Residential Address
    pin_code = Column(String(10), nullable=False)        # Pin Code
    phone = Column(String(20), nullable=False)           # 6 Mobile No
    email = Column(String(100), nullable=True)
    
    # 7 - 9 Birth & Govt Identity
    place_of_birth = Column(String(100), nullable=False) # 7 Place of Birth
    dob = Column(String(20), nullable=False)             # 8 Date of Birth
    aadhar_no = Column(String(20), nullable=False, index=True) # 9 Aadhar No (12 digits)

    # 10 - 12 Demographic Classifications
    gender = Column(String(20), nullable=False)          # 10 Gender (Male, Female, Trans Gender)
    religion = Column(String(50), nullable=False)        # 11 Minority Religion
    category = Column(String(50), nullable=False)        # 12 Category (OPEN, SC, ST, etc.)

    # Photo, Signature & Aadhar Document storage (Optional)
    photo_url = Column(Text, nullable=True)              # Candidate Photo Base64 / URL
    signature_url = Column(Text, nullable=True)          # Candidate Signature Base64 / URL
    aadhar_front_url = Column(Text, nullable=True)       # Optional Aadhar Card Front Image
    aadhar_back_url = Column(Text, nullable=True)        # Optional Aadhar Card Back Image

    # Academic Division Setup
    division = Column(String(50), nullable=False)        # Pre-Primary, School Section, Junior College
    standard = Column(String(50), nullable=False)        # Nursery, Jr. KG, Sr. KG, 1st - 12th
    section = Column(String(10), nullable=False, default="A")
    stream = Column(String(50), nullable=True)           # Science, Commerce, Arts (for 11th & 12th)
    academic_year = Column(String(20), nullable=False, default="2026-2027")
    
    # Advance Credit & Financial Balances
    advance_balance = Column(Float, nullable=False, default=0.0) # Accumulated Advance Credit
    
    # Legacy compatibility fields
    parent_name = Column(String(150), nullable=True)     # Auto-synced with Father/Mother name
    
    status = Column(String(20), nullable=False, default="Active") # Active, Passed, Left
    created_at = Column(DateTime(timezone=True), server_default=func.now())
