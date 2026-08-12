import sqlite3
import os
import sys

def map_and_import(source_db_path):
    if not os.path.exists(source_db_path):
        print(f"Error: Source database file not found at: {source_db_path}")
        return

    target_db_path = 'd:/Project/SMS/backend/school.db'
    if not os.path.exists(target_db_path):
        # Fallback to relative path if absolute path is different
        target_db_path = os.path.join(os.path.dirname(__file__), 'school.db')

    print(f"Source Database: {source_db_path}")
    print(f"Target Database: {target_db_path}")

    src_conn = sqlite3.connect(source_db_path)
    src_cursor = src_conn.cursor()
    
    tgt_conn = sqlite3.connect(target_db_path)
    tgt_cursor = tgt_conn.cursor()

    try:
        # Get all tables in source db
        src_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in src_cursor.fetchall()]
        
        # Identify the correct source table containing student records
        source_table = None
        for table in tables:
            src_cursor.execute(f"PRAGMA table_info('{table}')")
            cols = [c[1] for c in src_cursor.fetchall()]
            if 'firstName' in cols and 'lastName' in cols:
                source_table = table
                break
                
        if not source_table:
            # Fallback to any table named students/student
            for table in tables:
                if 'student' in table.lower():
                    source_table = table
                    break
                    
        if not source_table:
            print("Error: Could not automatically detect student table in source database.")
            print(f"Available tables in source: {tables}")
            return
            
        print(f"Detected Source Table: {source_table}")
        
        # Get target columns
        tgt_cursor.execute("PRAGMA table_info('students')")
        target_columns = {c[1] for c in tgt_cursor.fetchall()}
        
        # Fetch all records from source table
        src_cursor.execute(f"SELECT * FROM {source_table}")
        columns_desc = [description[0] for description in src_cursor.description]
        rows = src_cursor.fetchall()
        
        print(f"Found {len(rows)} records in source database. Mapping & Migrating...")
        
        imported_count = 0
        for row in rows:
            src_data = dict(zip(columns_desc, row))
            
            # Map source columns to target columns
            tgt_data = {}
            
            # Name
            tgt_data['first_name'] = src_data.get('firstName')
            tgt_data['middle_name'] = src_data.get('middleName')
            tgt_data['last_name'] = src_data.get('lastName')
            
            parts = [tgt_data['first_name'], tgt_data['middle_name'], tgt_data['last_name']]
            tgt_data['full_name'] = " ".join([p for p in parts if p]).strip()
            
            tgt_data['mother_name'] = src_data.get('motherName') or "Not Provided"
            tgt_data['parent_name'] = src_data.get('guardianName') or "Not Provided"
            
            # Contact & Address
            tgt_data['phone'] = src_data.get('mobileNo') or src_data.get('guardianMobile') or "0000000000"
            tgt_data['email'] = src_data.get('email') or ""
            tgt_data['address'] = src_data.get('address') or "Not Provided"
            tgt_data['pin_code'] = src_data.get('pinCode') or ""
            
            # Identity
            tgt_data['aadhar_no'] = src_data.get('aadharNo') or ""
            tgt_data['gender'] = src_data.get('gender') or "Male"
            tgt_data['dob'] = src_data.get('dob') or "2000-01-01"
            
            # Academic Details
            ac_year = src_data.get('academicYear') or "2026-2027"
            if ac_year == "2026-27":
                ac_year = "2026-2027"
            elif ac_year == "2025-26":
                ac_year = "2025-2026"
            elif ac_year == "2024-25":
                ac_year = "2024-2025"
            elif ac_year == "2023-24":
                ac_year = "2023-2024"
            tgt_data['academic_year'] = ac_year
            
            # Standard & Class Name
            std = src_data.get('className') or "1st"
            tgt_data['standard'] = std
            
            # Map division based on standard
            division = 'School Section'
            if std in ['Nursery', 'Jr. KG', 'Sr. KG']:
                division = 'Pre-Primary'
            elif std in ['11th', '12th']:
                division = 'Junior College'
            tgt_data['division'] = division
            
            tgt_data['section'] = 'A'
            tgt_data['stream'] = ''
            tgt_data['place_of_birth'] = src_data.get('city') or ""
            tgt_data['religion'] = 'Hindu'
            tgt_data['category'] = src_data.get('admissionCategory') or 'OPEN'
            
            # Images
            tgt_data['photo_url'] = ''
            tgt_data['signature_url'] = ''
            tgt_data['aadhar_front_url'] = ''
            tgt_data['aadhar_back_url'] = ''
            
            # Default numeric balances
            tgt_data['advance_balance'] = 0.0
            tgt_data['status'] = 'Active'
            tgt_data['created_at'] = src_data.get('createdAt') or src_data.get('created_at') or '2026-08-06 00:00:00'

            # Generate unique GR Number
            academic_year = tgt_data['academic_year']
            year_prefix = academic_year.split("-")[0]
            
            tgt_cursor.execute("SELECT MAX(CAST(SUBSTR(gr_no, 9) AS INTEGER)) FROM students WHERE gr_no LIKE ?", (f"GR-{year_prefix}-%",))
            max_idx = tgt_cursor.fetchone()[0]
            next_idx = (max_idx or 0) + 1
            gr_no = f"GR-{year_prefix}-{next_idx:04d}"
            tgt_data['gr_no'] = gr_no
            
            # Filter fields to only matching ones
            tgt_data_filtered = {k: v for k, v in tgt_data.items() if k in target_columns}
            
            # Insert record
            cols_str = ", ".join(tgt_data_filtered.keys())
            placeholders = ", ".join(["?" for _ in tgt_data_filtered])
            values = tuple(tgt_data_filtered.values())
            
            insert_query = f"INSERT INTO students ({cols_str}) VALUES ({placeholders})"
            tgt_cursor.execute(insert_query, values)
            
            # Increment index for database queries inside the loop
            imported_count += 1
            
        tgt_conn.commit()
        print(f"🎉 Migration Successful! Imported {imported_count} student records cleanly.")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        tgt_conn.rollback()
    finally:
        src_conn.close()
        tgt_conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide the source SQLite database file path.")
        print("Usage: python import_students.py <path_to_source_db>")
    else:
        map_and_import(sys.argv[1])
