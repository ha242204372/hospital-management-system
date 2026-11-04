#!/usr/bin/env python3
"""
Migrate MediCare HMS from SQLite (database/hospital.db) to local PostgreSQL.

Usage on your Mac:
  1. Make sure PostgreSQL is running.
  2. Install the driver if needed:
       pip install psycopg2-binary
  3. Set your password (or edit the defaults below):
       export PGPASSWORD=your_postgres_password
  4. Run from the project folder:
       python3 migrate_to_postgres.py

Environment variables (optional):
  PGHOST      default: localhost
  PGPORT      default: 5432
  PGUSER      default: postgres
  PGPASSWORD  (required)
  PGDATABASE  default: hospital
"""

import os
import sys
import sqlite3
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Missing driver. Install it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)

# ---------- config ----------
SQLITE_PATH = Path(__file__).parent / "database" / "hospital.db"
PGHOST = os.environ.get("PGHOST", "localhost")
PGPORT = int(os.environ.get("PGPORT", "5432"))
PGUSER = os.environ.get("PGUSER", "postgres")
PGPASSWORD = os.environ.get("PGPASSWORD", "")
PGDATABASE = os.environ.get("PGDATABASE", "hospital")

if not PGPASSWORD:
    print("Set your PostgreSQL password first:")
    print("  export PGPASSWORD=your_password")
    print("Then re-run this script.")
    sys.exit(1)

if not SQLITE_PATH.exists():
    print(f"SQLite file not found: {SQLITE_PATH}")
    sys.exit(1)

# Tables in dependency-safe order (parents before children)
TABLE_ORDER = [
    "departments",
    "staff",
    "patients",
    "users",
    "wards",
    "beds",
    "appointments",
    "encounters",
    "admissions",
    "lab_tests",
    "lab_orders",
    "medicines",
    "dispensing",
    "invoices",
    "invoice_items",
    "payments",
    "expenses",
    "assets",
    "audit_log",
    "settings",
]

# PostgreSQL CREATE statements (simplified, matching current SQLite schema)
PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS staff (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    specialization TEXT,
    phone TEXT,
    email TEXT,
    fee REAL DEFAULT 0,
    status TEXT DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    mrn TEXT UNIQUE,
    name TEXT NOT NULL,
    gender TEXT,
    dob TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    blood_group TEXT,
    allergies TEXT,
    emergency_contact TEXT,
    emergency_phone TEXT,
    created_at TEXT DEFAULT (CURRENT_DATE::text)
);
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    staff_id INTEGER,
    patient_id INTEGER
);
CREATE TABLE IF NOT EXISTS wards (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    daily_rate REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS beds (
    id SERIAL PRIMARY KEY,
    ward_id INTEGER NOT NULL REFERENCES wards(id),
    bed_no TEXT NOT NULL,
    status TEXT DEFAULT 'Available'
);
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES staff(id),
    date TEXT NOT NULL,
    time TEXT,
    reason TEXT,
    status TEXT DEFAULT 'Scheduled'
);
CREATE TABLE IF NOT EXISTS encounters (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES staff(id),
    date TEXT NOT NULL,
    bp TEXT,
    temperature TEXT,
    pulse TEXT,
    weight TEXT,
    diagnosis TEXT,
    notes TEXT,
    prescription TEXT
);
CREATE TABLE IF NOT EXISTS admissions (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES staff(id),
    bed_id INTEGER NOT NULL REFERENCES beds(id),
    admit_date TEXT NOT NULL,
    discharge_date TEXT,
    diagnosis TEXT,
    status TEXT DEFAULT 'Admitted'
);
CREATE TABLE IF NOT EXISTS lab_tests (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    price REAL DEFAULT 0,
    reference_range TEXT
);
CREATE TABLE IF NOT EXISTS lab_orders (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER REFERENCES staff(id),
    test_id INTEGER NOT NULL REFERENCES lab_tests(id),
    ordered_at TEXT,
    status TEXT DEFAULT 'Ordered',
    result TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS medicines (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 10,
    unit_price REAL DEFAULT 0,
    expiry_date TEXT,
    supplier TEXT
);
CREATE TABLE IF NOT EXISTS dispensing (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    quantity INTEGER NOT NULL,
    amount REAL,
    date TEXT
);
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    number TEXT UNIQUE,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    date TEXT,
    total REAL DEFAULT 0,
    paid REAL DEFAULT 0,
    status TEXT DEFAULT 'Unpaid',
    notes TEXT
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT,
    date TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    vendor TEXT,
    description TEXT,
    amount REAL NOT NULL,
    paid REAL DEFAULT 0,
    status TEXT DEFAULT 'Unpaid',
    method TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    purchase_date TEXT,
    cost REAL DEFAULT 0,
    residual_value REAL DEFAULT 0,
    status TEXT DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    at TEXT,
    "user" TEXT,
    action TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def main():
    print(f"SQLite source : {SQLITE_PATH}")
    print(f"PostgreSQL    : {PGUSER}@{PGHOST}:{PGPORT}/{PGDATABASE}")

    # 1. Connect to default 'postgres' db and create target database if needed
    admin = psycopg2.connect(host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname="postgres")
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PGDATABASE,))
        if not cur.fetchone():
            print(f"Creating database '{PGDATABASE}'...")
            cur.execute(f'CREATE DATABASE "{PGDATABASE}"')
        else:
            print(f"Database '{PGDATABASE}' already exists.")
    admin.close()

    # 2. Connect to target database and create schema
    pg = psycopg2.connect(host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname=PGDATABASE)
    pg.autocommit = False
    with pg.cursor() as cur:
        print("Creating tables...")
        cur.execute(PG_SCHEMA)
    pg.commit()

    # 3. Copy data
    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row
    with pg.cursor() as cur:
        for table in TABLE_ORDER:
            exists = sq.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                print(f"  {table}: skipped (not in SQLite)")
                continue
            rows = sq.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                print(f"  {table}: 0 rows")
                continue
            cols = rows[0].keys()
            col_list = ", ".join(f'"{c}"' if c == "user" else c for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            data = [tuple(r[c] for c in cols) for r in rows]
            cur.executemany(sql, data)
            print(f"  {table}: {len(data)} rows copied")
        for table in TABLE_ORDER:
            if table == "settings":
                continue
            try:
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))",
                    (table,),
                )
            except Exception:
                pass
    pg.commit()
    pg.close()
    sq.close()
    print("\nMigration complete.")
    print(f"You can now point the app at PostgreSQL with:")
    print(f"  DATABASE_URL=postgresql://{PGUSER}:****@{PGHOST}:{PGPORT}/{PGDATABASE}")


if __name__ == "__main__":
    main()
