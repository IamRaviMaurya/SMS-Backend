"""
Idempotent multi-tenant migration for an existing school.db (SQLite).

Safe to run repeatedly. Steps:
  1. tenants table + default tenant for pre-existing data
  2. users table (platform Super Admin + per-school admins) with bcrypt hashes
  3. tenant_id on every tenant-owned table (incl. payment_details) + backfill
  4. teachers.password -> teachers.password_hash (bcrypt)
  5. per-tenant UNIQUE indexes (gr_no, receipt_no, teacher email, user email)

Run:  python migrate_multi_tenant.py
Env:  SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD override the bootstrap platform login.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings  # noqa: E402
from app.core.security import get_password_hash, is_password_hash  # noqa: E402

DEFAULT_TENANT_ID = "default-tenant-001"

TENANT_TABLES = [
    "students", "fee_structures", "fee_payments", "payment_details", "advance_credits",
    "notices", "teachers", "attendance", "student_leaves", "homework", "lesson_plans",
    "exam_marks", "co_curricular_records", "teacher_leaves", "teacher_timetables",
]


def _db_path() -> str:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        print("This migration script only supports SQLite. For MySQL/Postgres use Alembic.")
        sys.exit(1)
    path = url.replace("sqlite:///", "", 1)
    return path if os.path.isabs(path) else os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip("./"))


def _columns(cur, table):
    return [r[1] for r in cur.execute(f"PRAGMA table_info('{table}')").fetchall()]


def _table_exists(cur, table):
    return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _add_column(cur, table, ddl):
    col = ddl.split()[0]
    if col in _columns(cur, table):
        print(f"  SKIP  {table}.{col} exists")
        return False
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    print(f"  OK    added {table}.{col}")
    return True


def _unique_index(cur, name, table, cols):
    dup_sql = f"SELECT {', '.join(cols)}, COUNT(*) c FROM {table} GROUP BY {', '.join(cols)} HAVING c > 1"
    dups = cur.execute(dup_sql).fetchall()
    if dups:
        print(f"  WARN  cannot create {name}: {len(dups)} duplicate group(s) in {table}({', '.join(cols)}), e.g. {dups[0]}")
        return
    cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({', '.join(cols)})")
    print(f"  OK    unique index {name}")


def migrate():
    db_path = _db_path()
    if not os.path.exists(db_path):
        print(f"ERROR: {db_path} not found. Run `python seed.py` for a fresh database instead.")
        sys.exit(1)
    print(f"Using database: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    # 1. tenants
    print("\n[1/5] tenants")
    cur.execute("""
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
    )""")
    cur.execute("""
    INSERT OR IGNORE INTO tenants (id, school_name, slug, contact_email, contact_phone, status, subscription_plan, student_limit)
    VALUES (?, 'Avdhoot Bhagwan Ram Vidyalaya', 'main', 'admin@school.com', '7276669858', 'VERIFIED', 'PREMIUM', 5000)
    """, (DEFAULT_TENANT_ID,))
    print("  OK    default tenant present")

    # 2. users
    print("\n[2/5] users")
    if not _table_exists(cur, "users"):
        cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'SCHOOL_ADMIN',
            full_name VARCHAR(100) NOT NULL,
            tenant_id VARCHAR(50) REFERENCES tenants(id) ON DELETE CASCADE,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            must_change_password BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login_at DATETIME
        )""")
        print("  OK    created users table")
    else:
        _add_column(cur, "users", "is_active BOOLEAN NOT NULL DEFAULT 1")
        _add_column(cur, "users", "must_change_password BOOLEAN NOT NULL DEFAULT 0")
        _add_column(cur, "users", "last_login_at DATETIME")
        # Old script stored plaintext in password_hash and gave super admins a tenant. Fix both.
        for uid, pw in cur.execute("SELECT id, password_hash FROM users").fetchall():
            if not is_password_hash(pw):
                cur.execute("UPDATE users SET password_hash=? WHERE id=?", (get_password_hash(pw), uid))
                print(f"  OK    hashed plaintext password for user id={uid}")
        cur.execute("UPDATE users SET tenant_id = NULL WHERE role = 'SUPER_ADMIN'")

    email = settings.SUPER_ADMIN_EMAIL.lower()
    exists = cur.execute("SELECT id FROM users WHERE lower(email)=? AND role='SUPER_ADMIN'", (email,)).fetchone()
    if not exists:
        cur.execute(
            "INSERT INTO users (email, password_hash, role, full_name, tenant_id) VALUES (?, ?, 'SUPER_ADMIN', 'Platform Super Admin', NULL)",
            (email, get_password_hash(settings.SUPER_ADMIN_PASSWORD)),
        )
        print(f"  OK    seeded Super Admin {email} (password from SUPER_ADMIN_PASSWORD env, default 'Admin@123')")
    else:
        print(f"  SKIP  Super Admin {email} exists")

    # Default tenant school admin so the legacy school can log in at /main/login
    if not cur.execute("SELECT 1 FROM users WHERE tenant_id=? AND role='SCHOOL_ADMIN'", (DEFAULT_TENANT_ID,)).fetchone():
        cur.execute(
            "INSERT INTO users (email, password_hash, role, full_name, tenant_id, must_change_password) VALUES (?, ?, 'SCHOOL_ADMIN', 'Principal / Accounts Administrator', ?, 1)",
            ("admin@school.com", get_password_hash("admin123"), DEFAULT_TENANT_ID),
        )
        print("  OK    seeded default School Admin admin@school.com / admin123 (must change on first login)")

    # 3. tenant_id columns
    print("\n[3/5] tenant_id columns")
    for table in TENANT_TABLES:
        if not _table_exists(cur, table):
            print(f"  SKIP  {table} does not exist")
            continue
        _add_column(cur, table, f"tenant_id VARCHAR(50) NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'")
        cur.execute(f"UPDATE {table} SET tenant_id = ? WHERE tenant_id IS NULL OR tenant_id = ''", (DEFAULT_TENANT_ID,))
        cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)")
    if _table_exists(cur, "payment_details") and _table_exists(cur, "fee_payments"):
        cur.execute("""
        UPDATE payment_details SET tenant_id = (
            SELECT fp.tenant_id FROM fee_payments fp WHERE fp.id = payment_details.payment_id
        ) WHERE EXISTS (SELECT 1 FROM fee_payments fp WHERE fp.id = payment_details.payment_id)
        """)
        print("  OK    payment_details.tenant_id backfilled from fee_payments")

    # 4. teacher passwords
    print("\n[4/5] teacher passwords")
    if _table_exists(cur, "teachers"):
        cols = _columns(cur, "teachers")
        if "password" in cols and "password_hash" not in cols:
            cur.execute("ALTER TABLE teachers RENAME COLUMN password TO password_hash")
            print("  OK    renamed teachers.password -> password_hash")
        elif "password_hash" not in cols:
            _add_column(cur, "teachers", "password_hash VARCHAR(255)")
        upgraded = 0
        for tid, pw in cur.execute("SELECT id, password_hash FROM teachers").fetchall():
            if pw and not is_password_hash(pw):
                cur.execute("UPDATE teachers SET password_hash=? WHERE id=?", (get_password_hash(pw), tid))
                upgraded += 1
        print(f"  OK    {upgraded} plaintext teacher password(s) hashed")

    # 5. per-tenant uniqueness
    print("\n[5/5] unique constraints")
    _unique_index(cur, "ux_students_tenant_gr_no", "students", ["tenant_id", "gr_no"])
    _unique_index(cur, "ux_fee_payments_tenant_receipt_no", "fee_payments", ["tenant_id", "receipt_no"])
    _unique_index(cur, "ux_teachers_tenant_email", "teachers", ["tenant_id", "email"])
    _unique_index(cur, "ux_users_tenant_email", "users", ["tenant_id", "email"])

    conn.commit()
    cur.execute("PRAGMA foreign_keys = ON")
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    migrate()
