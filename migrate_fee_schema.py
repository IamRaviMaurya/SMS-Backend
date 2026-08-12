"""
Migration script: Add new columns and tables for fee system enhancements.
Run this ONCE after updating the models.

Usage:
    cd d:\Project\SMS\backend
    python migrate_fee_schema.py
"""
import sqlite3
import os
import sys

# Find the database file
db_paths = [
    "school.db",
    os.path.join(os.path.dirname(__file__), "school.db"),
    r"d:\Project\SMS\backend\school.db",
]
db_path = None
for p in db_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("ERROR: school.db not found! Searched in:")
    for p in db_paths:
        print(f"  {p}")
    sys.exit(1)

print(f"Using database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

migrations = []

# 1. Add `description` column to fee_structures
try:
    cursor.execute("ALTER TABLE fee_structures ADD COLUMN description TEXT")
    migrations.append("fee_structures.description")
    print("✓ Added description column to fee_structures")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("  (already exists) fee_structures.description")
    else:
        print(f"  ERROR: {e}")

# 2. Add `notes` column to fee_payments
try:
    cursor.execute("ALTER TABLE fee_payments ADD COLUMN notes TEXT")
    migrations.append("fee_payments.notes")
    print("✓ Added notes column to fee_payments")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("  (already exists) fee_payments.notes")
    else:
        print(f"  ERROR: {e}")

# 3. Create advance_credits table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS advance_credits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id),
            amount REAL NOT NULL,
            reason VARCHAR(200),
            added_by VARCHAR(100) NOT NULL DEFAULT 'Admin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    migrations.append("advance_credits table")
    print("✓ Created advance_credits table")
except sqlite3.OperationalError as e:
    print(f"  ERROR creating advance_credits: {e}")

conn.commit()
conn.close()

print("\nMigration complete!")
print(f"Applied: {len(migrations)} changes")
for m in migrations:
    print(f"  + {m}")
