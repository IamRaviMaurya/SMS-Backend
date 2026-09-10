from app.models.tenant import Tenant, TenantMixin, TenantStatus, SubscriptionPlan
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.fee import FeeStructure, FeePayment, PaymentDetail, AdvanceCredit
from app.models.academic import (
    Teacher, Attendance, StudentLeave, Homework, LessonPlan,
    ExamMark, CoCurricular, Notice, TeacherLeave, TeacherTimetable
)

# Installs the automatic tenant-scoping hooks on SessionLocal (import side effect).
from app.core import tenancy  # noqa: E402,F401
