import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, engine, Base
from app.models import Student, FeeStructure, FeePayment, PaymentDetail
from app.services.fee_service import process_fee_collection
from app.schemas.fee import FeeCollectCreate, FeeItemCollect

MONTHS = [
    "June 2026", "July 2026", "August 2026", "September 2026",
    "October 2026", "November 2026", "December 2026", "January 2027",
    "February 2027", "March 2027", "April 2027", "May 2027"
]

def seed_database():
    # Re-create database schema with updated Student model
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("Seeding Monthly & Annual Fee Structures across Academic Divisions...")
        
        fee_structures = []

        # 1. Pre-Primary (Nursery, Jr. KG, Sr. KG) - Monthly Tuition Fee ₹2,000/mo + Annual Activity Fee ₹3,000
        for m in MONTHS:
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="Pre-Primary", standard="All", term=m, amount=2000, academic_year="2026-2027")
            )
        fee_structures.append(
            FeeStructure(category="Activity & Play Fee", division="Pre-Primary", standard="All", term="Annual", amount=3000, academic_year="2026-2027")
        )

        # 2. School Section (1st to 10th) - Monthly Tuition Fee ₹3,000/mo + Development & Computer Fees
        for m in MONTHS:
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="School Section", standard="All", term=m, amount=3000, academic_year="2026-2027")
            )
        fee_structures.append(
            FeeStructure(category="Development Fee", division="School Section", standard="All", term="Annual", amount=4000, academic_year="2026-2027")
        )
        fee_structures.append(
            FeeStructure(category="Computer & Lab Fee", division="School Section", standard="All", term="Annual", amount=2500, academic_year="2026-2027")
        )

        # 3. Junior College (11th & 12th) - Science ₹4,500/mo, Commerce ₹3,500/mo, Arts ₹3,000/mo
        for m in MONTHS:
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="Junior College", standard="11th", stream="Science", term=m, amount=4500, academic_year="2026-2027")
            )
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="Junior College", standard="12th", stream="Science", term=m, amount=4800, academic_year="2026-2027")
            )
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="Junior College", standard="11th", stream="Commerce", term=m, amount=3500, academic_year="2026-2027")
            )
            fee_structures.append(
                FeeStructure(category="Monthly Tuition Fee", division="Junior College", standard="11th", stream="Arts", term=m, amount=3000, academic_year="2026-2027")
            )

        fee_structures.append(
            FeeStructure(category="Science Practical Lab Fee", division="Junior College", standard="11th", stream="Science", term="Annual", amount=6000, academic_year="2026-2027")
        )

        db.add_all(fee_structures)
        db.commit()

        print("Seeding Sample Students with full official Indian admission form details...")
        students = [
            Student(
                gr_no="GR-2026-0001",
                last_name="Patel",
                first_name="Aarav",
                middle_name="Aniket",
                mother_name="Sunita",
                full_name="Aarav Aniket Patel",
                parent_name="Aniket Patel",
                address="B-402, Gokul Heights, Suburban Colony, Mumbai",
                pin_code="400001",
                phone="9820123456",
                email="aniket.patel@gmail.com",
                place_of_birth="Mumbai",
                dob="2020-04-12",
                aadhar_no="1234-5678-9012",
                gender="Male",
                religion="Non-Minority",
                category="OPEN",
                division="Pre-Primary",
                standard="Sr. KG",
                section="A",
                stream=None,
                academic_year="2026-2027",
                status="Active"
            ),
            Student(
                gr_no="GR-2026-0002",
                last_name="Sharma",
                first_name="Ananya",
                middle_name="Rajesh",
                mother_name="Meena",
                full_name="Ananya Rajesh Sharma",
                parent_name="Rajesh Sharma",
                address="12, Shanti Nagar, MG Road, Pune",
                pin_code="411001",
                phone="9876543210",
                email="rajesh.sharma@yahoo.com",
                place_of_birth="Pune",
                dob="2014-08-22",
                aadhar_no="9876-5432-1098",
                gender="Female",
                religion="Non-Minority",
                category="OBC",
                division="School Section",
                standard="7th",
                section="B",
                stream=None,
                academic_year="2026-2027",
                status="Active"
            ),
            Student(
                gr_no="GR-2026-0003",
                last_name="Agarwal",
                first_name="Agastya",
                middle_name="Sanjay",
                mother_name="Kavita",
                full_name="Agastya Sanjay Agarwal",
                parent_name="Sanjay Agarwal",
                address="701, Diamond Towers, Link Road, Thane",
                pin_code="400601",
                phone="9811223344",
                email="sanjay.agarwal@gmail.com",
                place_of_birth="Thane",
                dob="2009-02-14",
                aadhar_no="4567-8901-2345",
                gender="Male",
                religion="Non-Minority",
                category="OPEN",
                division="Junior College",
                standard="11th",
                section="A",
                stream="Science",
                academic_year="2026-2027",
                status="Active"
            ),
            Student(
                gr_no="GR-2026-0004",
                last_name="Deshmukh",
                first_name="Priya",
                middle_name="Vikas",
                mother_name="Radha",
                full_name="Priya Vikas Deshmukh",
                parent_name="Vikas Deshmukh",
                address="45, Green Park Society, Nashik",
                pin_code="422001",
                phone="9988776655",
                email="vikas.deshmukh@gmail.com",
                place_of_birth="Nashik",
                dob="2012-11-05",
                aadhar_no="3344-5566-7788",
                gender="Female",
                religion="Non-Minority",
                category="OPEN",
                division="School Section",
                standard="9th",
                section="C",
                stream=None,
                academic_year="2026-2027",
                status="Active"
            ),
        ]

        db.add_all(students)
        db.commit()

        print("Seeding Initial Fee Payment & Receipt for Student GR-2026-0002...")
        sample_student = db.query(Student).filter(Student.gr_no == "GR-2026-0002").first()
        if sample_student:
            collect_data = FeeCollectCreate(
                student_id=sample_student.id,
                payment_mode="UPI",
                transaction_ref="UPI/98124012/8890",
                items=[
                    FeeItemCollect(fee_head="Monthly Tuition Fee (June 2026)", amount=3000),
                    FeeItemCollect(fee_head="Monthly Tuition Fee (July 2026)", amount=3000),
                    FeeItemCollect(fee_head="Development Fee (Annual)", amount=4000)
                ],
                late_fine=200,
                discount=500,
                pending_due=30000,
                collected_by="Accounts Counter 1"
            )
            process_fee_collection(db, collect_data)

        # Import academic models to seed
        from app.models.academic import Teacher, Attendance, StudentLeave, Homework, LessonPlan, ExamMark, CoCurricular, Notice, TeacherLeave, TeacherTimetable

        print("Seeding Teachers & HR Profiles...")
        teachers = [
            Teacher(name="Verma Sir (Maths)", email="verma@school.com", phone="9898012345", assigned_class="7th", assigned_section="B", status="Active", password="teacher123"),
            Teacher(name="Patil Teacher (Science)", email="patil@school.com", phone="9898012346", assigned_class="9th", assigned_section="C", status="Active", password="teacher123"),
            Teacher(name="Desai Sir (English)", email="desai@school.com", phone="9898012347", assigned_class="11th", assigned_section="A", status="Active", password="teacher123")
        ]
        db.add_all(teachers)
        db.commit()

        # Fetch teacher ids
        t_verma = db.query(Teacher).filter(Teacher.name.like("%Verma%")).first()
        t_patil = db.query(Teacher).filter(Teacher.name.like("%Patil%")).first()

        print("Seeding Syllabus Lesson Plans...")
        lesson_plans = [
            LessonPlan(standard="7th", subject="Mathematics", chapter_name="Algebraic Expressions", completion_percentage=80, status="IN_PROGRESS"),
            LessonPlan(standard="7th", subject="Mathematics", chapter_name="Linear Equations", completion_percentage=100, status="COMPLETED"),
            LessonPlan(standard="9th", subject="Science", chapter_name="Laws of Motion", completion_percentage=45, status="IN_PROGRESS"),
            LessonPlan(standard="11th", subject="Physics", chapter_name="Thermodynamics", completion_percentage=10, status="IN_PROGRESS")
        ]
        db.add_all(lesson_plans)

        print("Seeding Teacher Timetable Schedules...")
        timetables = [
            TeacherTimetable(teacher_id=t_verma.id, day_of_week="Monday", period_no=1, standard="7th", section="B", subject="Mathematics", classroom="Room 102"),
            TeacherTimetable(teacher_id=t_verma.id, day_of_week="Monday", period_no=3, standard="8th", section="A", subject="Mathematics", classroom="Room 105"),
            TeacherTimetable(teacher_id=t_patil.id, day_of_week="Monday", period_no=2, standard="9th", section="C", subject="Science", classroom="Lab 1"),
            TeacherTimetable(teacher_id=t_patil.id, day_of_week="Tuesday", period_no=4, standard="10th", section="B", subject="Science", classroom="Room 204")
        ]
        db.add_all(timetables)

        print("Seeding Student Leave Requests...")
        student_aarav = db.query(Student).filter(Student.gr_no == "GR-2026-0001").first()
        student_ananya = db.query(Student).filter(Student.gr_no == "GR-2026-0002").first()
        
        leaves = []
        if student_aarav and student_ananya:
            leaves = [
                StudentLeave(student_id=student_aarav.id, start_date="2026-08-10", end_date="2026-08-12", reason="Family Marriage Function", status="PENDING"),
                StudentLeave(student_id=student_ananya.id, start_date="2026-08-05", end_date="2026-08-06", reason="Viral Fever Recovery", status="APPROVED", actioned_by="Verma Sir")
            ]
            db.add_all(leaves)

        print("Seeding Broadcast Notices & Circulars...")
        notices = [
            Notice(target_type="ALL", target_value=None, title="Independence Day Flag Hoisting", message="All students and parents are requested to gather in the school ground on 15th August at 7:30 AM in full uniform."),
            Notice(target_type="CLASS", target_value="School Section-7th-B", title="Maths Unit Test Syllabus Update", message="The unit test on 18th August will cover Chapter 1 (Integers) and Chapter 2 (Fractions) only."),
        ]
        db.add_all(notices)

        print("Seeding Teacher HR Leaves...")
        teacher_leaves = [
            TeacherLeave(teacher_id=t_verma.id, leave_type="CASUAL", start_date="2026-08-15", end_date="2026-08-16", reason="Personal work at hometown", status="PENDING")
        ]
        db.add_all(teacher_leaves)
        
        print("Seeding Exam Marks...")
        if student_ananya:
            marks = [
                ExamMark(student_id=student_ananya.id, exam_type="TERM_1", subject="Mathematics", marks_obtained=88.5, max_marks=100.0, remarks="Excellent performance"),
                ExamMark(student_id=student_ananya.id, exam_type="TERM_1", subject="Science", marks_obtained=92.0, max_marks=100.0, remarks="Highly curious student"),
            ]
            db.add_all(marks)

        print("Seeding CCE Co-Curricular Profiles...")
        if student_ananya:
            co_curriculars = [
                CoCurricular(student_id=student_ananya.id, sports_grade="A+", behavior_grade="A", attendance_percentage=96.4, remarks="Very active in volleyball and keeps class discipline.")
            ]
            db.add_all(co_curriculars)
        
        db.commit()

        print("Database Seeding Completed Successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
