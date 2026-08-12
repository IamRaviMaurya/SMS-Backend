from fastapi import FastAPI, Depends, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.api import auth_router, students_router, fees_router, academic_router
from app.services import student_service
import app.models # Ensure models are registered

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev flexibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(students_router, prefix=settings.API_V1_STR)
app.include_router(fees_router, prefix=settings.API_V1_STR)
app.include_router(academic_router, prefix=settings.API_V1_STR)

# --- Backward-Compatibility Aliases ---
@app.get(f"{settings.API_V1_STR}/admission/students")
def get_admission_students_alias(
    response: Response,
    division: Optional[str] = Query(None),
    standard: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    students = student_service.get_students(
        db, 
        division=division, 
        standard=standard, 
        section=section
    )
    return [
        {
            "id": s.id,
            "gr_no": s.gr_no,
            "full_name": s.full_name,
            "last_name": s.last_name,
            "first_name": s.first_name,
            "middle_name": s.middle_name,
            "mother_name": s.mother_name,
            "parent_name": s.parent_name,
            "phone": s.phone,
            "email": s.email,
            "dob": s.dob,
            "gender": s.gender,
            "blood_group": s.blood_group,
            "division": s.division,
            "standard": s.standard,
            "section": s.section,
            "roll_no": s.roll_no,
            "status": s.status
        }
        for s in students
    ]

@app.get("/")
def root():
    return {
        "message": "Welcome to Indian School Management System API",
        "version": settings.VERSION,
        "docs": "/docs"
    }

@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
