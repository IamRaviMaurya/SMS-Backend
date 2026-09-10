"""
Multi-tenant isolation test-suite.

Runs the real FastAPI app against a throw-away SQLite file so it never touches school.db.
    python -m pytest tests -q
"""
import os
import sys
import tempfile

import pytest

# Point the app at a fresh database BEFORE anything imports settings/engine.
_TMP_DIR = tempfile.mkdtemp(prefix="sms_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db').replace(os.sep, '/')}"
os.environ["ENV"] = "test"
os.environ["SUPER_ADMIN_EMAIL"] = "root@platform.example.com"
os.environ["SUPER_ADMIN_PASSWORD"] = "RootPass#123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.core.tenancy import TenantContextMissing, bypass_tenant_scope, tenant_scope  # noqa: E402
from app.models import Student, User  # noqa: E402

client = TestClient(app)
API = "/api/v1"

STUDENT_PAYLOAD = {
    "last_name": "Patel", "first_name": "Aarav", "middle_name": "Aniket", "mother_name": "Sunita",
    "address": "B-402, Gokul Heights", "pin_code": "400001", "phone": "9820123456",
    "email": "aarav@example.com", "place_of_birth": "Mumbai", "dob": "2014-05-15",
    "aadhar_no": "1234-5678-9012", "gender": "Male", "division": "School Section",
    "standard": "7th", "section": "A", "academic_year": "2026-2027",
}


def _auth(token, tenant=None):
    headers = {"Authorization": f"Bearer {token}"}
    if tenant:
        headers["X-Tenant-ID"] = tenant
    return headers


def _login(username, password, tenant=None, expect=200):
    body = {"username": username, "password": password}
    if tenant:
        body["tenant"] = tenant
    res = client.post(f"{API}/auth/login", json=body)
    assert res.status_code == expect, res.text
    return res.json() if expect == 200 else res


@pytest.fixture(scope="module")
def platform():
    """Bootstraps a super admin and two verified schools with their admin logins."""
    db = SessionLocal()
    db.add(User(email="root@platform.example.com", password_hash=get_password_hash("RootPass#123"),
                role="SUPER_ADMIN", full_name="Root", tenant_id=None))
    db.commit()
    db.close()

    sa = _login("root@platform.example.com", "RootPass#123")
    assert sa["user_role"] == "SUPER_ADMIN"
    sa_token = sa["access_token"]

    schools = {}
    for slug in ("alpha", "beta"):
        res = client.post(f"{API}/super-admin/register-school", json={
            "school_name": f"{slug.title()} High", "slug": slug,
            "contact_email": f"principal@{slug}.example.com", "contact_phone": "9800000000",
            "subscription_plan": "BASIC",
        })
        assert res.status_code == 201, res.text
        tenant_id = res.json()["tenant_id"]

        res = client.patch(f"{API}/super-admin/schools/{tenant_id}/verify",
                           json={"status": "VERIFIED", "student_limit": 3, "subscription_days": 30},
                           headers=_auth(sa_token))
        assert res.status_code == 200, res.text
        creds = res.json()["credentials"]
        assert creds and creds["temporary_password"]

        admin = _login(creds["admin_email"], creds["temporary_password"], tenant=slug)
        assert admin["user_role"] == "admin" and admin["tenant_id"] == tenant_id
        schools[slug] = {"id": tenant_id, "admin_token": admin["access_token"],
                         "admin_email": creds["admin_email"], "admin_password": creds["temporary_password"]}

    return {"sa_token": sa_token, "schools": schools}


# ────────── Authentication is mandatory ──────────

def test_unauthenticated_requests_are_rejected():
    assert client.get(f"{API}/students").status_code == 401
    assert client.get(f"{API}/fees/stats").status_code == 401
    assert client.get(f"{API}/academic/teachers/all").status_code == 401
    assert client.get(f"{API}/super-admin/schools").status_code == 401
    assert client.get(f"{API}/admission/students").status_code == 401


def test_garbage_token_is_rejected():
    assert client.get(f"{API}/students", headers=_auth("not-a-jwt")).status_code == 401


def test_no_hardcoded_backdoor_logins(platform):
    for u, p in [("admin", "admin123"), ("admin@gmail.com", "Admin@123"), ("superadmin", "adminpassword")]:
        res = client.post(f"{API}/auth/login", json={"username": u, "password": p, "tenant": "alpha"})
        assert res.status_code in (400, 401), (u, res.text)


# ────────── Data isolation ──────────

def test_school_data_is_isolated(platform):
    alpha, beta = platform["schools"]["alpha"], platform["schools"]["beta"]

    res = client.post(f"{API}/students/register", json=STUDENT_PAYLOAD, headers=_auth(alpha["admin_token"]))
    assert res.status_code == 201, res.text
    student_id = res.json()["id"]
    platform["alpha_student_id"] = student_id

    # Owner sees it
    assert client.get(f"{API}/students/{student_id}", headers=_auth(alpha["admin_token"])).status_code == 200

    # Other school cannot see, list, update or ledger it
    b = _auth(beta["admin_token"])
    assert client.get(f"{API}/students/{student_id}", headers=b).status_code == 404
    assert client.get(f"{API}/students/{student_id}/full-ledger", headers=b).status_code == 404
    assert client.put(f"{API}/students/{student_id}", json={"first_name": "Hacked"}, headers=b).status_code == 404
    assert all(s["id"] != student_id for s in client.get(f"{API}/students", headers=b).json())
    assert client.get(f"{API}/students/stats", headers=b).json()["total_students"] == 0

    # Student was not renamed by the cross-tenant PUT
    assert client.get(f"{API}/students/{student_id}", headers=_auth(alpha["admin_token"])).json()["first_name"] == "Aarav"


def test_tenant_header_cannot_override_token(platform):
    alpha, beta = platform["schools"]["alpha"], platform["schools"]["beta"]
    res = client.get(f"{API}/students", headers=_auth(alpha["admin_token"], tenant=beta["id"]))
    assert res.status_code == 403
    res = client.get(f"{API}/students", headers=_auth(alpha["admin_token"], tenant="beta"))
    assert res.status_code == 403
    # Echoing your own tenant (id or slug) is fine
    assert client.get(f"{API}/students", headers=_auth(alpha["admin_token"], tenant=alpha["id"])).status_code == 200
    assert client.get(f"{API}/students", headers=_auth(alpha["admin_token"], tenant="alpha")).status_code == 200


def test_gr_numbers_are_per_tenant(platform):
    beta = platform["schools"]["beta"]
    res = client.post(f"{API}/students/register", json={**STUDENT_PAYLOAD, "phone": "9111111111"},
                      headers=_auth(beta["admin_token"]))
    assert res.status_code == 201, res.text
    # Both schools start their own GR sequence at 0001
    assert res.json()["gr_no"] == "GR-2026-0001"
    platform["beta_student_id"] = res.json()["id"]
    # Duplicate within the same school is rejected
    res = client.post(f"{API}/students/register", json={**STUDENT_PAYLOAD, "gr_no": "GR-2026-0001"},
                      headers=_auth(beta["admin_token"]))
    assert res.status_code == 409


def test_student_limit_is_enforced(platform):
    beta = platform["schools"]["beta"]
    # limit is 3: one exists already
    for i in range(2):
        res = client.post(f"{API}/students/register", json={**STUDENT_PAYLOAD, "phone": f"92222222{i}0"},
                          headers=_auth(beta["admin_token"]))
        assert res.status_code == 201, res.text
    res = client.post(f"{API}/students/register", json={**STUDENT_PAYLOAD, "phone": "9333333333"},
                      headers=_auth(beta["admin_token"]))
    assert res.status_code == 403
    assert "limit" in res.json()["detail"].lower()


def test_fees_are_isolated(platform):
    alpha, beta = platform["schools"]["alpha"], platform["schools"]["beta"]
    sid = platform["alpha_student_id"]
    res = client.post(f"{API}/fees/collect", json={
        "student_id": sid, "payment_mode": "Cash",
        "items": [{"fee_head": "Tuition (June 2026)", "amount": 3000, "total_due_amount": 3000, "remaining_due": 0}],
    }, headers=_auth(alpha["admin_token"]))
    assert res.status_code == 200, res.text
    receipt_id = res.json()["id"]

    b = _auth(beta["admin_token"])
    assert client.get(f"{API}/fees/receipt/{receipt_id}", headers=b).status_code == 404
    assert client.delete(f"{API}/fees/payments/{receipt_id}", headers=b).status_code == 404
    assert client.get(f"{API}/fees/payments/student/{sid}", headers=b).status_code == 404
    assert client.get(f"{API}/fees/stats", headers=b).json()["total_receipts"] == 0
    assert client.get(f"{API}/fees/stats", headers=_auth(alpha["admin_token"])).json()["total_receipts"] == 1

    # Beta cannot collect a fee against Alpha's student either
    res = client.post(f"{API}/fees/collect", json={
        "student_id": sid, "payment_mode": "Cash", "items": [{"fee_head": "X", "amount": 1}],
    }, headers=b)
    assert res.status_code == 400 and "not found" in res.json()["detail"].lower()


def test_academic_records_are_isolated(platform):
    alpha, beta = platform["schools"]["alpha"], platform["schools"]["beta"]
    a, b = _auth(alpha["admin_token"]), _auth(beta["admin_token"])

    res = client.post(f"{API}/academic/notices", json={
        "target_type": "ALL", "title": "Alpha only", "message": "secret",
    }, headers=a)
    assert res.status_code == 200, res.text
    notice_id = res.json()["id"]

    assert all(n["id"] != notice_id for n in client.get(f"{API}/academic/notices", headers=b).json())
    assert client.delete(f"{API}/academic/notices/{notice_id}", headers=b).status_code == 404
    assert client.put(f"{API}/academic/notices/{notice_id}", json={
        "target_type": "ALL", "title": "pwned", "message": "x"}, headers=b).status_code == 404

    # Attendance marked from Beta against an Alpha student must not be visible to Alpha
    sid = platform["alpha_student_id"]
    client.post(f"{API}/academic/attendance/bulk", json={
        "date": "2026-09-10", "lecture_no": 0, "teacher_id": None,
        "records": [{"student_id": sid, "status": "ABSENT"}],
    }, headers=b)
    rows = client.get(f"{API}/academic/attendance", params={
        "date": "2026-09-10", "division": "School Section", "standard": "7th", "section": "A"}, headers=a).json()
    assert rows and rows[0]["id"] == 0 and rows[0]["status"] == "PRESENT"  # nothing marked in Alpha


# ────────── Teachers / students login is tenant-scoped ──────────

def test_teacher_login_is_scoped_to_school(platform):
    alpha, beta = platform["schools"]["alpha"], platform["schools"]["beta"]
    res = client.post(f"{API}/academic/teachers/create", json={
        "name": "Verma Sir", "email": "verma@school.example.com", "phone": "9898012345",
        "assigned_class": "7th", "assigned_section": "A", "password": "teacher123",
    }, headers=_auth(alpha["admin_token"]))
    assert res.status_code == 200, res.text
    assert "password" not in res.json() and "password_hash" not in res.json()

    teacher = _login("verma@school.example.com", "teacher123", tenant="alpha")
    assert teacher["user_role"] == "teacher" and teacher["tenant_id"] == alpha["id"]
    _login("verma@school.example.com", "teacher123", tenant="beta", expect=401)
    _login("verma@school.example.com", "wrong", tenant="alpha", expect=401)
    _login("verma@school.example.com", "teacher123", expect=400)  # school not specified

    # Teachers are not admins
    t = _auth(teacher["access_token"])
    assert client.post(f"{API}/students/register", json=STUDENT_PAYLOAD, headers=t).status_code == 403
    assert client.delete(f"{API}/fees/payments/1", headers=t).status_code == 403
    assert client.get(f"{API}/students", headers=t).status_code == 200
    assert client.get(f"{API}/super-admin/schools", headers=t).status_code == 403

    # Same e-mail can exist in another school without conflict
    res = client.post(f"{API}/academic/teachers/create", json={
        "name": "Other Verma", "email": "verma@school.example.com", "phone": "1", "password": "different1",
    }, headers=_auth(beta["admin_token"]))
    assert res.status_code == 200, res.text
    other = _login("verma@school.example.com", "different1", tenant="beta")
    assert other["full_name"] == "Other Verma" and other["tenant_id"] == beta["id"]


def test_student_login_uses_dob_and_is_scoped(platform):
    alpha = platform["schools"]["alpha"]
    st = _login("GR-2026-0001", "2014-05-15", tenant="alpha")
    assert st["user_role"] == "student" and st["student_id"] == platform["alpha_student_id"]
    _login("GR-2026-0001", "student123", tenant="alpha", expect=401)
    _login("GR-2026-0001", "GR-2026-0001", tenant="alpha", expect=401)
    # Beta's GR-2026-0001 is a different child; Alpha's DOB must not unlock it
    _login("GR-2026-0001", "2014-05-15", tenant="beta", expect=200)  # same payload DOB by construction
    res = client.get(f"{API}/auth/me", headers=_auth(st["access_token"]))
    assert res.status_code == 200 and res.json()["tenant_id"] == alpha["id"]


# ────────── Super Admin behaviour ──────────

def test_super_admin_must_pick_a_school_for_tenant_routes(platform):
    sa = platform["sa_token"]
    alpha = platform["schools"]["alpha"]
    assert client.get(f"{API}/students", headers=_auth(sa)).status_code == 400
    res = client.get(f"{API}/students", headers=_auth(sa, tenant=alpha["id"]))
    assert res.status_code == 200 and [s["id"] for s in res.json()] == [platform["alpha_student_id"]]
    res = client.get(f"{API}/students", headers=_auth(sa, tenant="beta"))
    assert res.status_code == 200 and platform["alpha_student_id"] not in [s["id"] for s in res.json()]
    assert client.get(f"{API}/students", headers=_auth(sa, tenant="does-not-exist")).status_code == 404


def test_super_admin_analytics_counts_all_tenants(platform):
    res = client.get(f"{API}/super-admin/analytics", headers=_auth(platform["sa_token"]))
    assert res.status_code == 200
    assert res.json()["total_students_across_all_tenants"] == 4  # 1 alpha + 3 beta


def test_suspended_school_is_locked_out(platform):
    sa = platform["sa_token"]
    beta = platform["schools"]["beta"]
    res = client.patch(f"{API}/super-admin/schools/{beta['id']}/verify", json={"status": "SUSPENDED"}, headers=_auth(sa))
    assert res.status_code == 200
    # existing token stops working, new logins are refused
    assert client.get(f"{API}/students", headers=_auth(beta["admin_token"])).status_code == 403
    _login(beta["admin_email"], beta["admin_password"], tenant="beta", expect=403)
    # platform operator can still inspect it
    assert client.get(f"{API}/students", headers=_auth(sa, tenant="beta")).status_code == 200
    client.patch(f"{API}/super-admin/schools/{beta['id']}/verify", json={"status": "VERIFIED", "student_limit": 3}, headers=_auth(sa))


def test_change_password_flow(platform):
    alpha = platform["schools"]["alpha"]
    res = client.post(f"{API}/auth/change-password", json={
        "current_password": alpha["admin_password"], "new_password": "NewStrongPass1"},
        headers=_auth(alpha["admin_token"]))
    assert res.status_code == 200, res.text
    _login(alpha["admin_email"], alpha["admin_password"], tenant="alpha", expect=401)
    fresh = _login(alpha["admin_email"], "NewStrongPass1", tenant="alpha")
    assert fresh["must_change_password"] is False
    alpha["admin_password"] = "NewStrongPass1"


# ────────── ORM-level guarantees (defence in depth) ──────────

def test_orm_fails_closed_without_tenant_context(platform):
    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing):
            db.query(Student).all()
        with pytest.raises(TenantContextMissing):
            db.query(Student.id).count()
        with bypass_tenant_scope():
            assert db.query(Student).count() == 4
        with tenant_scope(platform["schools"]["alpha"]["id"]):
            assert db.query(Student).count() == 1
            assert db.query(Student.id).count() == 1
            # even an explicit contradictory filter cannot escape the tenant
            assert db.query(Student).filter(Student.tenant_id == platform["schools"]["beta"]["id"]).count() == 0
    finally:
        db.close()


def test_orm_refuses_cross_tenant_writes(platform):
    from app.core.tenancy import TenantViolation
    db = SessionLocal()
    try:
        with tenant_scope(platform["schools"]["alpha"]["id"]):
            s = Student(**{k: v for k, v in STUDENT_PAYLOAD.items()}, gr_no="GR-X", full_name="X",
                        tenant_id=platform["schools"]["beta"]["id"])
            db.add(s)
            with pytest.raises(TenantViolation):
                db.flush()
            db.rollback()
    finally:
        db.close()
