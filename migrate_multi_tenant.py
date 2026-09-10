import sqlite3
import os
import sys

db_path = "school.db"
if not os.path.exists(db_path):
    print(f"ERROR: {db_path} not found!")
    sys.exit(1)

print(f"Using database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Create tenants table
create_tenants_sql = """
CREATE TABLE IF NOT EXISTS tenants (
    id VARCHAR(50) PRIMARY KEY,
    school_name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255) UNIQUE,
    logo_url TEXT,
    primary_color VARCHAR(20) DEFAULT '#10B981',
    secondary_color VARCHAR(20) DEFAULT '#072654',
    contact_email VARCHAR(100) NOT NULL,
    contact_phone VARCHAR(20) NOT NULL,
    address TEXT,
    kyc_document_url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'VERIFIED',
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'PREMIUM',
    student_limit INTEGER DEFAULT 1000,
    subscription_expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
"""
cursor.execute(create_tenants_sql)
print("OK: Verified tenants table exists")

# 2. Insert Default Tenant for Existing Data
cursor.execute("""
INSERT OR IGNORE INTO tenants (id, school_name, slug, contact_email, contact_phone, status, subscription_plan, student_limit)
VALUES ('default-tenant-001', 'Avdhoot Bhagwan Ram Vidyalaya', 'main', 'admin@school.com', '7276669858', 'VERIFIED', 'PREMIUM', 5000);
""")
print("OK: Seeded default tenant ('default-tenant-001')")

# 3. Add tenant_id column to existing entity tables
tables = [
    "students",
    "fee_structures",
    "fee_payments",
    "notices",
    "teachers",
    "attendance",
    "student_leaves",
    "homework",
    "lesson_plans",
    "exam_marks",
    "co_curricular_records",
    "teacher_leaves",
    "teacher_timetables",
    "advance_credits"
]

applied_count = 0
for table in tables:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id VARCHAR(50) NOT NULL DEFAULT 'default-tenant-001'")
        applied_count += 1
        print(f"OK: Added tenant_id column to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"SKIP (already exists): {table}.tenant_id")
        else:
            print(f"INFO ({table}): {e}")

    # Update any null tenant_id values
    cursor.execute(f"UPDATE {table} SET tenant_id = 'default-tenant-001' WHERE tenant_id IS NULL OR tenant_id = ''")

conn.commit()

# Verify tables in SQLite
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = [r[0] for r in cursor.fetchall()]
print("\nAll database tables:", all_tables)

tenant_count = cursor.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
print(f"Total tenants in DB: {tenant_count}")

conn.close()
print(f"\nMigration complete! Applied changes to {applied_count} tables.")
