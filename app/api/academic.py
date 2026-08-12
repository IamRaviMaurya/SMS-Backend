from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.academic import (
    Teacher, Attendance, StudentLeave, Homework, LessonPlan,
    ExamMark, CoCurricular, Notice, TeacherLeave, TeacherTimetable
)
from app.models.student import Student
from app.schemas.academic import (
    TeacherCreate, TeacherResponse, AttendanceResponse, AttendanceBulkCreate, AttendanceRecordItem,
    StudentLeaveResponse, StudentLeaveCreate, HomeworkResponse, HomeworkCreate,
    LessonPlanResponse, LessonPlanCreate, ExamMarkResponse, ExamMarkBulkCreate, ExamMarkRecord,
    CoCurricularResponse, CoCurricularCreate, NoticeResponse, NoticeCreate,
    TeacherLeaveResponse, TeacherLeaveCreate, TeacherTimetableResponse
)

router = APIRouter(prefix="/academic", tags=["Academic & HR Management"])

# --- Teachers ---
@router.get("/teachers/all", response_model=List[TeacherResponse])
def get_all_teachers(db: Session = Depends(get_db)):
    return db.query(Teacher).all()

@router.post("/teachers/create", response_model=TeacherResponse)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    existing = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Teacher with this email already exists.")
    
    new_teacher = Teacher(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        assigned_class=payload.assigned_class,
        assigned_section=payload.assigned_section,
        status=payload.status,
        password=payload.password or "teacher123"
    )
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    return new_teacher

@router.put("/teachers/{teacher_id}/update", response_model=TeacherResponse)
def update_teacher(teacher_id: int, payload: TeacherCreate, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    
    if payload.email != teacher.email:
        existing = db.query(Teacher).filter(Teacher.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Teacher with this email already exists.")
            
    teacher.name = payload.name
    teacher.email = payload.email
    teacher.phone = payload.phone
    teacher.assigned_class = payload.assigned_class
    teacher.assigned_section = payload.assigned_section
    teacher.status = payload.status
    if payload.password:
        teacher.password = payload.password
        
    db.commit()
    db.refresh(teacher)
    return teacher

@router.delete("/teachers/{teacher_id}/delete")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    
    db.delete(teacher)
    db.commit()
    return {"message": "Teacher deleted successfully."}

# --- Attendance ---
@router.get("/attendance", response_model=List[AttendanceResponse])
def get_attendance(
    date: str,
    division: str,
    standard: str,
    section: str,
    lecture_no: int = 0,
    db: Session = Depends(get_db)
):
    # Fetch all students in the class
    students = db.query(Student).filter(
        Student.division == division,
        Student.standard == standard,
        Student.section == section,
        Student.status == "Active"
    ).all()

    results = []
    for s in students:
        # Check if attendance is already marked
        att = db.query(Attendance).filter(
            Attendance.student_id == s.id,
            Attendance.date == date,
            Attendance.lecture_no == lecture_no
        ).first()

        results.append(
            AttendanceResponse(
                id=att.id if att else 0,
                student_id=s.id,
                student_name=s.full_name,
                gr_no=s.gr_no,
                gender=s.gender,
                date=date,
                status=att.status if att else "PRESENT", # default UI value
                lecture_no=lecture_no,
                marked_by_teacher_id=att.marked_by_teacher_id if att else None
            )
        )
    return results

@router.post("/attendance/bulk")
def mark_attendance_bulk(payload: AttendanceBulkCreate, db: Session = Depends(get_db)):
    saved = 0
    for rec in payload.records:
        # Check if already exists
        att = db.query(Attendance).filter(
            Attendance.student_id == rec.student_id,
            Attendance.date == payload.date,
            Attendance.lecture_no == payload.lecture_no
        ).first()

        if att:
            att.status = rec.status
            att.marked_by_teacher_id = payload.teacher_id
        else:
            new_att = Attendance(
                student_id=rec.student_id,
                date=payload.date,
                status=rec.status,
                lecture_no=payload.lecture_no,
                marked_by_teacher_id=payload.teacher_id
            )
            db.add(new_att)
        saved += 1
    db.commit()
    return {"message": f"Attendance marked for {saved} students"}

@router.get("/attendance/history")
def get_attendance_history(
    start_date: str,
    end_date: str,
    standard: str,
    section: str,
    division: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Fetch all students in the class
    student_query = db.query(Student).filter(
        Student.standard == standard,
        Student.section == section,
        Student.status == "Active"
    )
    if division:
        student_query = student_query.filter(Student.division == division)
    students = student_query.all()
    student_ids = [s.id for s in students]
    student_map = {s.id: s for s in students}

    # Fetch all attendance records in date range
    records = db.query(Attendance).filter(
        Attendance.student_id.in_(student_ids) if student_ids else False,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()

    # Map records by student_id and date
    summaries = {}
    for s in students:
        summaries[s.id] = {
            "student_id": s.id,
            "student_name": s.full_name,
            "gr_no": s.gr_no,
            "gender": s.gender,
            "attendance": {}  # date -> status
        }

    for r in records:
        if r.student_id in summaries:
            summaries[r.student_id]["attendance"][r.date] = r.status

    return list(summaries.values())

# --- Student Leaves ---
@router.get("/student-leaves", response_model=List[StudentLeaveResponse])
def get_student_leaves(
    standard: Optional[str] = None,
    section: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(StudentLeave)
    
    if standard or section:
        student_query = db.query(Student.id)
        if standard:
            student_query = student_query.filter(Student.standard == standard)
        if section:
            student_query = student_query.filter(Student.section == section)
        student_ids = [s[0] for s in student_query.all()]
        query = query.filter(StudentLeave.student_id.in_(student_ids) if student_ids else False)
        
    if start_date:
        query = query.filter(StudentLeave.start_date >= start_date)
    if end_date:
        query = query.filter(StudentLeave.end_date <= end_date)
        
    leaves = query.order_by(StudentLeave.id.desc()).all()
    results = []
    for l in leaves:
        student = db.query(Student).filter(Student.id == l.student_id).first()
        res = StudentLeaveResponse.model_validate(l)
        res.student_name = student.full_name if student else "Unknown"
        res.gr_no = student.gr_no if student else "N/A"
        results.append(res)
    return results

@router.post("/student-leaves", response_model=StudentLeaveResponse)
def apply_student_leave(payload: StudentLeaveCreate, db: Session = Depends(get_db)):
    new_leave = StudentLeave(**payload.model_dump())
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)
    return new_leave

@router.put("/student-leaves/{leave_id}/status")
def update_student_leave_status(
    leave_id: int,
    status: str = Query(..., description="APPROVED or REJECTED"),
    actioned_by: str = Query(..., description="Name of teacher/admin actioning"),
    db: Session = Depends(get_db)
):
    leave = db.query(StudentLeave).filter(StudentLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    leave.status = status
    leave.actioned_by = actioned_by
    db.commit()
    return {"message": f"Leave request status updated to {status} successfully"}

# --- Homework ---
@router.get("/homework", response_model=List[HomeworkResponse])
def get_homework(
    division: str = "All",
    standard: str = "All",
    section: str = "All",
    db: Session = Depends(get_db)
):
    query = db.query(Homework)
    if division != "All":
        query = query.filter(Homework.division == division)
    if standard != "All":
        query = query.filter(Homework.standard == standard)
    if section != "All":
        query = query.filter(Homework.section == section)
    return query.order_by(Homework.id.desc()).all()

@router.post("/homework", response_model=HomeworkResponse)
def upload_homework(payload: HomeworkCreate, db: Session = Depends(get_db)):
    new_hw = Homework(**payload.model_dump())
    db.add(new_hw)
    db.commit()
    db.refresh(new_hw)
    return new_hw

# --- Lesson Planner ---
@router.get("/lesson-plan", response_model=List[LessonPlanResponse])
def get_lesson_plans(
    standard: str = "All",
    subject: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(LessonPlan)
    if standard != "All":
        query = query.filter(LessonPlan.standard == standard)
    if subject:
        query = query.filter(LessonPlan.subject == subject)
    return query.order_by(LessonPlan.id.desc()).all()

@router.post("/lesson-plan", response_model=LessonPlanResponse)
def create_lesson_plan(payload: LessonPlanCreate, db: Session = Depends(get_db)):
    new_plan = LessonPlan(**payload.model_dump())
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return new_plan

@router.put("/lesson-plan/{plan_id}/progress")
def update_lesson_progress(
    plan_id: int,
    progress: int = Query(..., ge=0, le=100),
    db: Session = Depends(get_db)
):
    plan = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    plan.completion_percentage = progress
    plan.status = "COMPLETED" if progress == 100 else "IN_PROGRESS"
    db.commit()
    return {"message": "Lesson progress updated successfully"}

# --- Examination Marks ---
@router.get("/marks", response_model=List[ExamMarkResponse])
def get_exam_marks(
    exam_type: str,
    subject: str,
    division: str,
    standard: str,
    section: str,
    db: Session = Depends(get_db)
):
    # Fetch all students in the class
    students = db.query(Student).filter(
        Student.division == division,
        Student.standard == standard,
        Student.section == section,
        Student.status == "Active"
    ).all()

    results = []
    for s in students:
        mark = db.query(ExamMark).filter(
            ExamMark.student_id == s.id,
            ExamMark.exam_type == exam_type,
            ExamMark.subject == subject
        ).first()

        results.append(
            ExamMarkResponse(
                id=mark.id if mark else 0,
                student_id=s.id,
                student_name=s.full_name,
                gr_no=s.gr_no,
                exam_type=exam_type,
                subject=subject,
                marks_obtained=mark.marks_obtained if mark else 0.0,
                max_marks=mark.max_marks if mark else 100.0,
                remarks=mark.remarks if mark else ""
            )
        )
    return results

@router.get("/marks/student/{student_id}", response_model=List[ExamMarkResponse])
def get_student_marks(student_id: int, db: Session = Depends(get_db)):
    marks = db.query(ExamMark).filter(ExamMark.student_id == student_id).all()
    results = []
    student = db.query(Student).filter(Student.id == student_id).first()
    for m in marks:
        results.append(
            ExamMarkResponse(
                id=m.id,
                student_id=m.student_id,
                student_name=student.full_name if student else "Unknown",
                gr_no=student.gr_no if student else "N/A",
                exam_type=m.exam_type,
                subject=m.subject,
                marks_obtained=m.marks_obtained,
                max_marks=m.max_marks,
                remarks=m.remarks
            )
        )
    return results

@router.post("/marks/bulk")
def save_exam_marks_bulk(payload: ExamMarkBulkCreate, db: Session = Depends(get_db)):
    saved = 0
    for rec in payload.records:
        mark = db.query(ExamMark).filter(
            ExamMark.student_id == rec.student_id,
            ExamMark.exam_type == payload.exam_type,
            ExamMark.subject == payload.subject
        ).first()

        if mark:
            mark.marks_obtained = rec.marks_obtained
            mark.max_marks = rec.max_marks or 100.0
            mark.remarks = rec.remarks or 'Evaluated'
        else:
            new_mark = ExamMark(
                student_id=rec.student_id,
                exam_type=payload.exam_type,
                subject=payload.subject,
                marks_obtained=rec.marks_obtained,
                max_marks=rec.max_marks or 100.0,
                remarks=rec.remarks or 'Evaluated'
            )
            db.add(new_mark)
        saved += 1
    db.commit()
    return {"message": f"Examination marks updated successfully for {saved} students"}

# --- Co-Curricular & Grades ---
@router.get("/co-curricular/{student_id}", response_model=Optional[CoCurricularResponse])
def get_student_co_curricular(student_id: int, db: Session = Depends(get_db)):
    rec = db.query(CoCurricular).filter(CoCurricular.student_id == student_id).first()
    if rec:
        student = db.query(Student).filter(Student.id == student_id).first()
        res = CoCurricularResponse.model_validate(rec)
        res.student_name = student.full_name if student else "Unknown"
        return res
    return None

@router.post("/co-curricular", response_model=CoCurricularResponse)
def save_co_curricular(payload: CoCurricularCreate, db: Session = Depends(get_db)):
    rec = db.query(CoCurricular).filter(CoCurricular.student_id == payload.student_id).first()
    if rec:
        rec.sports_grade = payload.sports_grade
        rec.behavior_grade = payload.behavior_grade
        rec.attendance_percentage = payload.attendance_percentage
        rec.remarks = payload.remarks
        db.commit()
        db.refresh(rec)
        return rec
    else:
        new_rec = CoCurricular(**payload.model_dump())
        db.add(new_rec)
        db.commit()
        db.refresh(new_rec)
        return new_rec

# --- Parent Notices / Circular Board ---
@router.get("/notices", response_model=List[NoticeResponse])
def get_notices(
    target_type: Optional[str] = None,
    target_value: Optional[str] = None,
    standard: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Notice)
    if standard and section:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                (Notice.standard == standard) & (Notice.section == section),
                Notice.target_type == "ALL",
                Notice.standard.is_(None)
            )
        )
    elif target_type:
        query = query.filter(Notice.target_type == target_type)
    return query.order_by(Notice.id.desc()).all()

@router.post("/notices", response_model=NoticeResponse)
def broadcast_notice(payload: NoticeCreate, db: Session = Depends(get_db)):
    new_notice = Notice(**payload.model_dump())
    db.add(new_notice)
    db.commit()
    db.refresh(new_notice)
    return new_notice

@router.put("/notices/{notice_id}", response_model=NoticeResponse)
def update_notice(notice_id: int, payload: NoticeCreate, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    notice.title = payload.title
    notice.message = payload.message
    if payload.posted_by:
        notice.posted_by = payload.posted_by
    if payload.standard:
        notice.standard = payload.standard
    if payload.section:
        notice.section = payload.section
    db.commit()
    db.refresh(notice)
    return notice

@router.delete("/notices/{notice_id}")
def delete_notice(notice_id: int, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    db.delete(notice)
    db.commit()
    return {"message": "Notice deleted successfully"}

# --- Teacher HR Panel & Self Service ---
@router.get("/teachers/{teacher_id}/timetable", response_model=List[TeacherTimetableResponse])
def get_teacher_timetable(teacher_id: int, db: Session = Depends(get_db)):
    return db.query(TeacherTimetable).filter(TeacherTimetable.teacher_id == teacher_id).all()

@router.get("/teachers/{teacher_id}/leaves", response_model=List[TeacherLeaveResponse])
def get_teacher_leaves(teacher_id: int, db: Session = Depends(get_db)):
    leaves = db.query(TeacherLeave).filter(TeacherLeave.teacher_id == teacher_id).all()
    results = []
    for l in leaves:
        teacher = db.query(Teacher).filter(Teacher.id == l.teacher_id).first()
        res = TeacherLeaveResponse.model_validate(l)
        res.teacher_name = teacher.name if teacher else "Unknown"
        results.append(res)
    return results

@router.post("/teachers/leaves", response_model=TeacherLeaveResponse)
def apply_teacher_leave(payload: TeacherLeaveCreate, db: Session = Depends(get_db)):
    new_leave = TeacherLeave(**payload.model_dump())
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)
    return new_leave

@router.get("/teachers/{teacher_id}/pay-slips")
def get_teacher_pay_slips(teacher_id: int, db: Session = Depends(get_db)):
    # Standard dynamic salary pay slip structure demonstration
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher record not found")
    
    # Mock payroll calculation logic
    return [
        {
            "month": "July 2026",
            "basic_salary": 45000.0,
            "allowances": 8500.0,
            "deductions": 2300.0,
            "net_paid": 51200.0,
            "payment_date": "2026-08-01",
            "payment_mode": "Bank Transfer"
        },
        {
            "month": "June 2026",
            "basic_salary": 45000.0,
            "allowances": 8500.0,
            "deductions": 2500.0,
            "net_paid": 51000.0,
            "payment_date": "2026-07-01",
            "payment_mode": "Bank Transfer"
        }
    ]

@router.get("/teachers/substitution-alerts")
def get_substitution_alerts(db: Session = Depends(get_db)):
    # Demo alert card when another teacher leaves class
    return [
        {
            "id": 1,
            "absent_teacher_name": "Sharma Sir (Maths)",
            "day": "Today",
            "period": "Period 3 (11:30 AM - 12:15 PM)",
            "class_assigned": "School Section - 7th - A",
            "subject": "Substitution Lecture (Practice sums)"
        }
    ]

@router.get("/teacher-self-service/dashboard")
def get_teacher_dashboard_stats(
    standard: str = Query("7th"),
    section: str = Query("B"),
    db: Session = Depends(get_db)
):
    class_strength = db.query(Student).filter(
        Student.standard == standard,
        Student.section == section,
        Student.status == "Active"
    ).count()

    return {
        "class_strength": class_strength,
        "standard": standard,
        "section": section
    }

