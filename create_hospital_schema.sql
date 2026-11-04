-- MediCare HMS — PostgreSQL schema
-- Run with:
--   psql -U postgres -h localhost -d hospital -f create_hospital_schema.sql
-- (Create the database first: CREATE DATABASE hospital;)

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- Staff
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

-- Patients
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

-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    staff_id INTEGER,
    patient_id INTEGER
);

-- Wards
CREATE TABLE IF NOT EXISTS wards (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    daily_rate REAL DEFAULT 0
);

-- Beds
CREATE TABLE IF NOT EXISTS beds (
    id SERIAL PRIMARY KEY,
    ward_id INTEGER NOT NULL REFERENCES wards(id),
    bed_no TEXT NOT NULL,
    status TEXT DEFAULT 'Available'
);

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES staff(id),
    date TEXT NOT NULL,
    time TEXT,
    reason TEXT,
    status TEXT DEFAULT 'Scheduled'
);

-- Encounters
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

-- Admissions
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

-- Lab tests
CREATE TABLE IF NOT EXISTS lab_tests (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    price REAL DEFAULT 0,
    reference_range TEXT
);

-- Lab orders
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

-- Medicines
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

-- Dispensing
CREATE TABLE IF NOT EXISTS dispensing (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    quantity INTEGER NOT NULL,
    amount REAL,
    date TEXT
);

-- Invoices
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

-- Invoice items
CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount REAL NOT NULL
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT,
    date TEXT
);

-- Expenses
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

-- Assets
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    purchase_date TEXT,
    cost REAL DEFAULT 0,
    residual_value REAL DEFAULT 0,
    status TEXT DEFAULT 'Active'
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    at TEXT,
    "user" TEXT,
    action TEXT,
    detail TEXT
);

-- Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
