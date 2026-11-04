"""Database connection, relational schema DDL, query helpers, and billing helpers."""
import sqlite3
import datetime as dt
from app.config import DB_PATH

# Active DB file path (can be overridden by tests via server.DB or db.ACTIVE_DB)
ACTIVE_DB = DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL, role TEXT NOT NULL, staff_id INTEGER, patient_id INTEGER);
CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT);
CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
  department_id INTEGER REFERENCES departments(id), specialization TEXT, phone TEXT, email TEXT,
  fee REAL DEFAULT 0, status TEXT DEFAULT 'Active');
CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY, mrn TEXT UNIQUE, name TEXT NOT NULL, gender TEXT, dob TEXT,
  phone TEXT, email TEXT, address TEXT, blood_group TEXT, allergies TEXT, emergency_contact TEXT, emergency_phone TEXT,
  created_at TEXT DEFAULT (date('now')));
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  doctor_id INTEGER NOT NULL REFERENCES staff(id), date TEXT NOT NULL, time TEXT, reason TEXT, status TEXT DEFAULT 'Scheduled');
CREATE TABLE IF NOT EXISTS encounters(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  doctor_id INTEGER NOT NULL REFERENCES staff(id), date TEXT NOT NULL, bp TEXT, temperature TEXT, pulse TEXT, weight TEXT,
  diagnosis TEXT, notes TEXT, prescription TEXT);
CREATE TABLE IF NOT EXISTS wards(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, type TEXT, daily_rate REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS beds(id INTEGER PRIMARY KEY, ward_id INTEGER NOT NULL REFERENCES wards(id), bed_no TEXT NOT NULL,
  status TEXT DEFAULT 'Available');
CREATE TABLE IF NOT EXISTS admissions(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  doctor_id INTEGER NOT NULL REFERENCES staff(id), bed_id INTEGER NOT NULL REFERENCES beds(id), admit_date TEXT NOT NULL,
  discharge_date TEXT, diagnosis TEXT, status TEXT DEFAULT 'Admitted');
CREATE TABLE IF NOT EXISTS lab_tests(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT, price REAL DEFAULT 0, reference_range TEXT);
CREATE TABLE IF NOT EXISTS lab_orders(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  doctor_id INTEGER REFERENCES staff(id), test_id INTEGER NOT NULL REFERENCES lab_tests(id), ordered_at TEXT, status TEXT DEFAULT 'Ordered',
  result TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS medicines(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT, stock INTEGER DEFAULT 0,
  reorder_level INTEGER DEFAULT 10, unit_price REAL DEFAULT 0, expiry_date TEXT, supplier TEXT);
CREATE TABLE IF NOT EXISTS dispensing(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  medicine_id INTEGER NOT NULL REFERENCES medicines(id), quantity INTEGER NOT NULL, amount REAL, date TEXT);
CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, number TEXT UNIQUE, patient_id INTEGER NOT NULL REFERENCES patients(id),
  date TEXT, total REAL DEFAULT 0, paid REAL DEFAULT 0, status TEXT DEFAULT 'Unpaid', notes TEXT);
CREATE TABLE IF NOT EXISTS invoice_items(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  description TEXT NOT NULL, amount REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  amount REAL NOT NULL, method TEXT, date TEXT);
CREATE TABLE IF NOT EXISTS prescriptions(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
  doctor_id INTEGER REFERENCES staff(id), encounter_id INTEGER, medicine TEXT NOT NULL, dosage TEXT, frequency TEXT,
  duration TEXT, instructions TEXT, date TEXT);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, at TEXT DEFAULT (datetime('now')), user TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

DEFAULT_SETTINGS = {
    "hospital_name": "VizMedCare",
    "tagline": "Hospital Management System · EHR · IPD · Lab · Pharmacy · Billing",
    "logo_icon": "✚",
    "currency": "PKR",
    "address": "Main Boulevard, Gulberg III, Lahore, Pakistan",
    "phone": "+92-42-111-222-333",
    "emergency_phone": "1122 / +92-42-111-911-911",
    "email": "info@medicare-hospital.pk",
    "website": "www.medicare-hospital.pk",
    "tax_id": "NTN-8492015-7",
    "mrn_prefix": "MRN",
    "invoice_prefix": "INV",
    "invoice_footer": "Thank you for choosing our hospital. Wishing you good health.",
    "default_theme": "indigo",
}


def get_settings(conn):
    _exec(conn, "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    stored = {r["key"]: r["value"] for r in rows(conn, "SELECT key, value FROM settings")}
    out = dict(DEFAULT_SETTINGS)
    for k, v in stored.items():
        if v is not None and v != "":
            out[k] = v
    return out


def save_settings(conn, data):
    _exec(conn, "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    for k in DEFAULT_SETTINGS:
        if k in data and data[k] is not None:
            _exec(conn,
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, str(data[k]).strip()),
            )
    return get_settings(conn)



def ensure_extra_tables(conn):
    """Create tables/columns added after initial migration. Each statement is isolated."""
    stmts = [
        """CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL REFERENCES patients(id),
            doctor_id INTEGER REFERENCES staff(id),
            encounter_id INTEGER,
            medicine TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            duration TEXT,
            instructions TEXT,
            date TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS mar (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL REFERENCES patients(id),
            medicine TEXT NOT NULL,
            dose TEXT,
            route TEXT,
            scheduled_time TEXT,
            given_time TEXT,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT,
            nurse TEXT
        )""",
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS visit_type TEXT DEFAULT 'In-person'",
    ]
    for sql in stmts:
        try:
            _exec(conn, sql)
            if USE_POSTGRES:
                conn.commit()
        except Exception:
            if USE_POSTGRES:
                conn.rollback()

def today():
    return dt.date.today().isoformat()



import os
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

def connect(db_path=None):
    if USE_POSTGRES:
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
        c = psycopg2.connect(DATABASE_URL)
        c.autocommit = False
        return c
    # SQLite fallback
    c = sqlite3.connect(db_path or ACTIVE_DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def _adapt_sql(sql):
    """Convert SQLite ? placeholders to PostgreSQL %s when needed."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql

def _exec(conn, sql, args=()):
    sql = _adapt_sql(sql)
    if USE_POSTGRES:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur
    return conn.execute(sql, args)

def rows(conn, sql, args=()):
    sql = _adapt_sql(sql)
    if USE_POSTGRES:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
    return [dict(r) for r in conn.execute(sql, args).fetchall()]

def one(conn, sql, args=()):
    sql = _adapt_sql(sql)
    if USE_POSTGRES:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            r = cur.fetchone()
            return dict(r) if r else None
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None

def scalar(conn, sql, args=()):
    sql = _adapt_sql(sql)
    if USE_POSTGRES:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            r = cur.fetchone()
            return (r[0] or 0) if r else 0
    r = conn.execute(sql, args).fetchone()
    return (r[0] or 0) if r else 0

def audit(conn, user, action, detail):
    col = '"user"' if USE_POSTGRES else "user"
    _exec(conn, f"INSERT INTO audit_log({col},action,detail) VALUES(?,?,?)", (user["username"] if user else "system", action, detail))


def recompute(conn, inv_id):
    total = scalar(conn, "SELECT SUM(amount) FROM invoice_items WHERE invoice_id=?", (inv_id,))
    paid = scalar(conn, "SELECT SUM(amount) FROM payments WHERE invoice_id=?", (inv_id,))
    status = "Paid" if total > 0 and paid >= total - 0.001 else ("Partial" if paid > 0 else "Unpaid")
    _exec(conn, "UPDATE invoices SET total=?, paid=?, status=? WHERE id=?", (total, paid, status, inv_id))


def new_invoice(conn, patient_id, date=None, notes=None):
    n = scalar(conn, "SELECT MAX(id) FROM invoices") + 1
    pfx = (get_settings(conn).get("invoice_prefix") or "INV").strip().rstrip("-")
    cur = _exec(conn, "INSERT INTO invoices(number,patient_id,date,notes) VALUES(?,?,?,?)",
        (f"{pfx}-{n:05d}", patient_id, date or today(), notes))
    if USE_POSTGRES:
        return cur.fetchone()[0] if cur.description else None
    return cur.lastrowid


def add_charge(conn, patient_id, desc, amount):
    inv = one(
        conn,
        "SELECT id FROM invoices WHERE patient_id=? AND status IN ('Unpaid','Partial') ORDER BY id DESC LIMIT 1",
        (patient_id,),
    )
    inv_id = inv["id"] if inv else new_invoice(conn, patient_id)
    _exec(conn, "INSERT INTO invoice_items(invoice_id,description,amount) VALUES(?,?,?)", (inv_id, desc, amount))
    recompute(conn, inv_id)
    return inv_id
