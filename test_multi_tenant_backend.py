import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from main import app
from app.core.database import SessionLocal
from app.models.tenant import Tenant, TenantStatus

client = TestClient(app)

print("=== Starting Multi-Tenant Backend Integration Tests ===")

# 1. Health Check
res = client.get("/api/v1/health")
assert res.status_code == 200
print("OK: Health Check Passed:", res.json())

# 2. Public School Registration
reg_payload = {
    "school_name": "Greenwood High International",
    "slug": "greenwood",
    "contact_email": "principal@greenwood.edu.in",
    "contact_phone": "9812345678",
    "address": "123 Campus Way, Bangalore",
    "subscription_plan": "BASIC"
}
res = client.post("/api/v1/super-admin/register-school", json=reg_payload)
assert res.status_code in [201, 400], f"Registration failed: {res.text}"

if res.status_code == 201:
    data = res.json()
    new_tenant_id = data["tenant_id"]
    print("OK: Public School Self-Registration Successful:", data)
else:
    print("INFO: School slug 'greenwood' already registered from previous run")
    db = SessionLocal()
    t = db.query(Tenant).filter(Tenant.slug == "greenwood").first()
    new_tenant_id = t.id
    db.close()

# 3. Super Admin List Schools Queue
res = client.get("/api/v1/super-admin/schools")
assert res.status_code == 200
schools = res.json()
print(f"OK: Super Admin Verification Queue List ({len(schools)} schools found):")
for s in schools:
    print(f"  - [{s['status']}] {s['school_name']} (slug: {s['slug']})")

# 4. Super Admin Approve / Verify School
verify_payload = {
    "status": "VERIFIED",
    "student_limit": 500,
    "subscription_days": 365
}
res = client.patch(f"/api/v1/super-admin/schools/{new_tenant_id}/verify", json=verify_payload)
assert res.status_code == 200
v_data = res.json()
print("OK: Super Admin Verification & Onboarding Action:")
print(f"  - Message: {v_data['message']}")
print(f"  - Status: {v_data['status']}")
print(f"  - Credentials Generated: {v_data['credentials']}")

# 5. Global SaaS Platform Analytics
res = client.get("/api/v1/super-admin/analytics")
assert res.status_code == 200
analytics = res.json()
print("OK: Global SaaS Platform Analytics Metrics:")
print(f"  - Total Schools: {analytics['total_schools']}")
print(f"  - Active Verified Schools: {analytics['active_schools']}")
print(f"  - Total Enrolled Students (All Tenants): {analytics['total_students_across_all_tenants']}")
print(f"  - Estimated MRR: INR {analytics['estimated_mrr_inr']:,.2f}")
print(f"  - Plan Breakdown: {analytics['plans_breakdown']}")

print("\n=== ALL MULTI-TENANT BACKEND TESTS PASSED CLEANLY! ===")
