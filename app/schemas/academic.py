from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# --- Teacher Schemas ---
class TeacherBase(BaseModel):
    name: str
    email: str
    phone: str
    assigned_class: Optional[str] = None
    assigned_section: Optional[str] = None
    status: Optional[str] = "Active"

class TeacherCreate(TeacherBase):
    password: Optional[str] = "teacher123"

class TeacherResponse(TeacherBase):
    id: int
    password: Optional[str] = "teacher123"

    class Config:
        from_attributes = True

# --- Attendance Schemas ---
class AttendanceBase(BaseModel):
    student_id: int
    date: str
    status: str # PRESENT, ABSENT, LATE, HALF_DAY
    lecture_no: Optional[int] = 0
    marked_by_teacher_id: Optional[int] = None

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceRecordItem(BaseModel):
    """Slim record inside bulk save — date/lecture_no are top-level payload fields"""
    student_id: int
    status: str  # PRESENT, ABSENT, LATE, HALF_DAY

class AttendanceResponse(AttendanceBase):
    id: int
    student_name: Optional[str] = None
    gr_no: Optional[str] = None
    gender: Optional[str] = None

    class Config:
        from_attributes = True

class AttendanceBulkCreate(BaseModel):
    date: str
    division: str
    standard: str
    section: str
    lecture_no: Optional[int] = 0
    teacher_id: Optional[int] = None
    records: List[AttendanceRecordItem]

# --- Student Leave Schemas ---
class StudentLeaveBase(BaseModel):
    student_id: int
    start_date: str
    end_date: str
    reason: str
    status: Optional[str] = "PENDING"
    actioned_by: Optional[str] = None

class StudentLeaveCreate(StudentLeaveBase):
    pass

class StudentLeaveResponse(StudentLeaveBase):
    id: int
    student_name: Optional[str] = None
    gr_no: Optional[str] = None

    class Config:
        from_attributes = True

# --- Homework Schemas ---
class HomeworkBase(BaseModel):
    division: str
    standard: str
    section: str
    subject: str
    title: str
    description: str
    attachment_url: Optional[str] = None
    deadline: str

class HomeworkCreate(HomeworkBase):
    pass

class HomeworkResponse(HomeworkBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Lesson Plan Schemas ---
class LessonPlanBase(BaseModel):
    standard: str
    subject: str
    chapter_name: str
    completion_percentage: int
    status: Optional[str] = "IN_PROGRESS"

class LessonPlanCreate(LessonPlanBase):
    pass

class LessonPlanResponse(LessonPlanBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Exam Mark Schemas ---
class ExamMarkBase(BaseModel):
    student_id: int
    exam_type: str # UNIT_TEST_1, TERM_1, UNIT_TEST_2, FINALS
    subject: str
    marks_obtained: float
    max_marks: Optional[float] = 100.0
    remarks: Optional[str] = None

class ExamMarkCreate(ExamMarkBase):
    pass

class ExamMarkRecord(BaseModel):
    """Single record inside a bulk save - no exam_type/subject needed (top-level fields)"""
    student_id: int
    marks_obtained: float
    max_marks: Optional[float] = 100.0
    remarks: Optional[str] = None

class ExamMarkResponse(ExamMarkBase):
    id: int
    student_name: Optional[str] = None
    gr_no: Optional[str] = None

    class Config:
        from_attributes = True

class ExamMarkBulkCreate(BaseModel):
    exam_type: str
    subject: str
    records: List[ExamMarkRecord]

# --- Co-Curricular Schemas ---
class CoCurricularBase(BaseModel):
    student_id: int
    sports_grade: Optional[str] = "A"
    behavior_grade: Optional[str] = "A"
    attendance_percentage: Optional[float] = 100.0
    remarks: Optional[str] = None

class CoCurricularCreate(CoCurricularBase):
    pass

class CoCurricularResponse(CoCurricularBase):
    id: int
    student_name: Optional[str] = None

    class Config:
        from_attributes = True

# --- Notice Schemas ---
class NoticeBase(BaseModel):
    target_type: str # ALL, CLASS, STUDENT
    target_value: Optional[str] = None
    standard: Optional[str] = None
    section: Optional[str] = None
    posted_by: Optional[str] = None
    title: str
    message: str

class NoticeCreate(NoticeBase):
    pass

class NoticeResponse(NoticeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Teacher Leave Schemas ---
class TeacherLeaveBase(BaseModel):
    teacher_id: int
    leave_type: str # CASUAL, SICK, EARNED
    start_date: str
    end_date: str
    reason: str
    status: Optional[str] = "PENDING"

class TeacherLeaveCreate(TeacherLeaveBase):
    pass

class TeacherLeaveResponse(TeacherLeaveBase):
    id: int
    teacher_name: Optional[str] = None

    class Config:
        from_attributes = True

# --- Teacher Timetable Schemas ---
class TeacherTimetableBase(BaseModel):
    teacher_id: int
    day_of_week: str
    period_no: int
    standard: str
    section: str
    subject: str
    classroom: Optional[str] = None

class TeacherTimetableResponse(TeacherTimetableBase):
    id: int

    class Config:
        from_attributes = True
