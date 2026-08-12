from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20), nullable=False)
    assigned_class = Column(String(50))  # e.g., "7th"
    assigned_section = Column(String(10)) # e.g., "A"
    status = Column(String(20), default="Active") # Active, Inactive
    password = Column(String(100), default="teacher123")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(String(20), nullable=False) # YYYY-MM-DD
    status = Column(String(20), nullable=False) # PRESENT, ABSENT, LATE, HALF_DAY
    lecture_no = Column(Integer, default=0) # 0 means full-day attendance
    marked_by_teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)

class StudentLeave(Base):
    __tablename__ = "student_leaves"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    start_date = Column(String(20), nullable=False) # YYYY-MM-DD
    end_date = Column(String(20), nullable=False) # YYYY-MM-DD
    reason = Column(String(255), nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED
    actioned_by = Column(String(100)) # Admin or Teacher name

class Homework(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, index=True)
    division = Column(String(50), nullable=False) # Pre-Primary, School Section, Junior College
    standard = Column(String(50), nullable=False)
    section = Column(String(10), nullable=False)
    subject = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    attachment_url = Column(String(255))
    deadline = Column(String(20), nullable=False) # YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.utcnow)

class LessonPlan(Base):
    __tablename__ = "lesson_plans"

    id = Column(Integer, primary_key=True, index=True)
    standard = Column(String(50), nullable=False)
    subject = Column(String(50), nullable=False)
    chapter_name = Column(String(100), nullable=False)
    completion_percentage = Column(Integer, default=0) # 0 to 100
    status = Column(String(20), default="IN_PROGRESS") # IN_PROGRESS, COMPLETED
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExamMark(Base):
    __tablename__ = "exam_marks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_type = Column(String(50), nullable=False) # UNIT_TEST_1, TERM_1, UNIT_TEST_2, FINALS
    subject = Column(String(50), nullable=False)
    marks_obtained = Column(Float, nullable=False)
    max_marks = Column(Float, default=100.0)
    remarks = Column(String(150))

class CoCurricular(Base):
    __tablename__ = "co_curricular_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    sports_grade = Column(String(5), default="A")
    behavior_grade = Column(String(5), default="A")
    attendance_percentage = Column(Float, default=100.0)
    remarks = Column(String(255))

class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String(20), nullable=False) # ALL, CLASS, STUDENT
    target_value = Column(String(100)) # e.g., "School Section-7th-A" or "GR-2026-0001"
    standard = Column(String(50), nullable=True)
    section = Column(String(10), nullable=True)
    posted_by = Column(String(100), nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TeacherLeave(Base):
    __tablename__ = "teacher_leaves"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    leave_type = Column(String(20), nullable=False) # CASUAL, SICK, EARNED
    start_date = Column(String(20), nullable=False) # YYYY-MM-DD
    end_date = Column(String(20), nullable=False) # YYYY-MM-DD
    reason = Column(String(255), nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED

class TeacherTimetable(Base):
    __tablename__ = "teacher_timetables"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    day_of_week = Column(String(20), nullable=False) # Monday, Tuesday...
    period_no = Column(Integer, nullable=False) # 1, 2, 3, 4, 5
    standard = Column(String(50), nullable=False)
    section = Column(String(10), nullable=False)
    subject = Column(String(50), nullable=False)
    classroom = Column(String(20))
