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
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, at TEXT DEFAULT (datetime('now')), user TEXT, action TEXT, detail TEXT);
"""


def today():
    return dt.date.today().isoformat()


def connect(db_path=None):
    c = sqlite3.connect(db_path or ACTIVE_DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def one(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


def scalar(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return (r[0] or 0) if r else 0


def audit(conn, user, action, detail):
    conn.execute(
        "INSERT INTO audit_log(user,action,detail) VALUES(?,?,?)",
        (user["username"] if user else "system", action, detail),
    )


def recompute(conn, inv_id):
    total = scalar(conn, "SELECT SUM(amount) FROM invoice_items WHERE invoice_id=?", (inv_id,))
    paid = scalar(conn, "SELECT SUM(amount) FROM payments WHERE invoice_id=?", (inv_id,))
    status = "Paid" if total > 0 and paid >= total - 0.001 else ("Partial" if paid > 0 else "Unpaid")
    conn.execute("UPDATE invoices SET total=?, paid=?, status=? WHERE id=?", (total, paid, status, inv_id))


def new_invoice(conn, patient_id, date=None, notes=None):
    n = scalar(conn, "SELECT MAX(id) FROM invoices") + 1
    cur = conn.execute(
        "INSERT INTO invoices(number,patient_id,date,notes) VALUES(?,?,?,?)",
        (f"INV-{n:05d}", patient_id, date or today(), notes),
    )
    return cur.lastrowid


def add_charge(conn, patient_id, desc, amount):
    inv = one(
        conn,
        "SELECT id FROM invoices WHERE patient_id=? AND status IN ('Unpaid','Partial') ORDER BY id DESC LIMIT 1",
        (patient_id,),
    )
    inv_id = inv["id"] if inv else new_invoice(conn, patient_id)
    conn.execute("INSERT INTO invoice_items(invoice_id,description,amount) VALUES(?,?,?)", (inv_id, desc, amount))
    recompute(conn, inv_id)
    return inv_id
