"""Demo database seeding & migration into the dedicated `database/` directory."""
import os
import shutil
import random
import datetime as dt
from app.config import BLOODS, DB_PATH, LEGACY_DB_PATH
import app.models.db as db_mod
from app.models.db import SCHEMA, connect, rows, one, scalar, recompute
from app.controllers.auth_controller import hash_pw
from app.controllers.crud_controller import create, discharge


def seed(conn):
    random.seed(42)
    sysu = {"username": "seed", "role": "Admin"}
    T = dt.date.today()

    def day(n):
        return (T + dt.timedelta(days=n)).isoformat()

    depts = ["Cardiology", "Neurology", "Orthopedics", "Pediatrics", "Gynecology", "General Medicine", "Emergency", "Radiology"]
    for d in depts:
        conn.execute("INSERT INTO departments(name,description) VALUES(?,?)", (d, f"{d} department"))
    dids = {r["name"]: r["id"] for r in rows(conn, "SELECT * FROM departments")}
    docs = [
        ("Dr. Amelia Hart", "Cardiology", "Interventional Cardiologist", 900),
        ("Dr. Rahul Mehta", "Neurology", "Neurologist", 850),
        ("Dr. Sofia Alvarez", "Orthopedics", "Orthopedic Surgeon", 800),
        ("Dr. Liam O'Connor", "Pediatrics", "Pediatrician", 600),
        ("Dr. Priya Nair", "Gynecology", "Obstetrician", 750),
        ("Dr. Omar Haddad", "General Medicine", "Internist", 500),
        ("Dr. Chen Wei", "Emergency", "Emergency Physician", 700),
        ("Dr. Hannah Fischer", "Radiology", "Radiologist", 650),
    ]
    for n, dp, sp, fee in docs:
        conn.execute(
            "INSERT INTO staff(name,role,department_id,specialization,phone,email,fee) VALUES(?,?,?,?,?,?,?)",
            (n, "Doctor", dids[dp], sp, "+1-555-01%02d" % random.randint(0, 99), n.split()[-1].lower() + "@medicare.example", fee),
        )
    others = [
        ("Nina Patel", "Nurse", "Emergency"),
        ("Tom Becker", "Nurse", "General Medicine"),
        ("Sara Khan", "Receptionist", None),
        ("Marco Silva", "Pharmacist", None),
        ("Lena Novak", "Lab Technician", None),
        ("George Adams", "Accountant", None),
    ]
    for n, r, dp in others:
        conn.execute(
            "INSERT INTO staff(name,role,department_id,phone,email) VALUES(?,?,?,?,?)",
            (n, r, dids.get(dp), "+1-555-02%02d" % random.randint(0, 99), n.split()[0].lower() + "@medicare.example"),
        )
    accounts = [
        ("admin", "System Administrator", "Admin", "admin123"),
        ("doctor", "Dr. Amelia Hart", "Doctor", "doctor123"),
        ("nurse", "Nina Patel", "Nurse", "nurse123"),
        ("reception", "Sara Khan", "Receptionist", "reception123"),
        ("pharmacy", "Marco Silva", "Pharmacist", "pharmacy123"),
        ("lab", "Lena Novak", "Lab Technician", "lab123"),
        ("accounts", "George Adams", "Accountant", "accounts123"),
    ]
    for u, n, r, p in accounts:
        conn.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)", (u, hash_pw(p), n, r))

    wards = [
        ("General Ward A", "General", 800),
        ("General Ward B", "General", 800),
        ("Private Rooms", "Private", 2500),
        ("ICU", "ICU", 6000),
        ("Maternity", "Maternity", 1800),
        ("Pediatric Ward", "Pediatric", 1200),
    ]
    for n, t, r in wards:
        cur = conn.execute("INSERT INTO wards(name,type,daily_rate) VALUES(?,?,?)", (n, t, r))
        for i in range(1, {"ICU": 6, "Private Rooms": 6}.get(n, 8) + 1):
            conn.execute("INSERT INTO beds(ward_id,bed_no) VALUES(?,?)", (cur.lastrowid, f"{n[0]}{i:02d}"))

    tests = [
        ("Complete Blood Count", "Hematology", 350, "WBC 4-11 x10^9/L"),
        ("Blood Glucose (Fasting)", "Biochemistry", 120, "70-100 mg/dL"),
        ("Lipid Profile", "Biochemistry", 600, "LDL < 100 mg/dL"),
        ("Liver Function Test", "Biochemistry", 700, "ALT 7-56 U/L"),
        ("Kidney Function Test", "Biochemistry", 650, "Creatinine 0.6-1.3 mg/dL"),
        ("Urine Routine", "Pathology", 150, "Normal"),
        ("Thyroid Profile (TSH)", "Biochemistry", 500, "0.4-4.0 mIU/L"),
        ("Chest X-Ray", "Radiology", 450, "—"),
        ("ECG", "Other", 300, "Normal sinus rhythm"),
        ("MRI Brain", "Radiology", 6500, "—"),
        ("Blood Culture", "Microbiology", 900, "No growth"),
        ("HbA1c", "Biochemistry", 450, "< 5.7%"),
    ]
    conn.executemany("INSERT INTO lab_tests(name,category,price,reference_range) VALUES(?,?,?,?)", tests)

    meds = [
        ("Paracetamol 500mg", "Analgesic", 400, 100, 2.5),
        ("Amoxicillin 500mg", "Antibiotic", 250, 80, 12),
        ("Metformin 500mg", "Antidiabetic", 300, 80, 4),
        ("Atorvastatin 20mg", "Statin", 180, 60, 9),
        ("Amlodipine 5mg", "Antihypertensive", 220, 60, 5),
        ("Omeprazole 20mg", "Antacid", 35, 50, 6),
        ("Ibuprofen 400mg", "Analgesic", 300, 80, 3),
        ("Cetirizine 10mg", "Antihistamine", 150, 40, 2),
        ("Insulin Glargine", "Antidiabetic", 18, 25, 450),
        ("Salbutamol Inhaler", "Respiratory", 60, 20, 180),
        ("Azithromycin 250mg", "Antibiotic", 140, 50, 28),
        ("ORS Sachet", "Rehydration", 500, 100, 1.5),
        ("Aspirin 75mg", "Antiplatelet", 90, 40, 1.8),
        ("Ceftriaxone 1g Inj", "Antibiotic", 12, 30, 85),
        ("Diclofenac Gel", "Topical", 70, 25, 55),
    ]
    for i, (n, c, s, rl, p) in enumerate(meds):
        exp = day(random.choice([30, 60, 200, 400, 600, 800]) if i != 5 else 45)
        conn.execute(
            "INSERT INTO medicines(name,category,stock,reorder_level,unit_price,expiry_date,supplier) VALUES(?,?,?,?,?,?,?)",
            (n, c, s, rl, p, exp, random.choice(["PharmaCorp", "MediSupply Ltd", "HealthPlus"])),
        )

    first = [
        "Aarav", "Olivia", "Noah", "Emma", "Liam", "Sophia", "Mason", "Ava", "Ethan", "Mia",
        "Lucas", "Isabella", "Yusuf", "Fatima", "Ahmed", "Layla", "Carlos", "Maria", "Ivan", "Anna",
        "Kenji", "Yuki", "Priya", "Rohan", "Zara", "Omar", "Hana", "David", "Grace", "Samuel",
    ]
    last = ["Smith", "Johnson", "Khan", "Patel", "Garcia", "Kim", "Nguyen", "Ali", "Brown", "Silva", "Rossi", "Müller", "Ivanov", "Sato", "Hassan", "Cohen"]
    cities = ["12 Maple St", "45 Oak Ave", "8 River Rd", "221 Sunset Blvd", "17 Hill View", "90 Lake Dr"]
    for i in range(45):
        g = random.choice(["Male", "Female"])
        dob = (T - dt.timedelta(days=random.randint(200, 365 * 82))).isoformat()
        cid = create(
            conn,
            "patients",
            dict(
                name=f"{random.choice(first)} {random.choice(last)}",
                gender=g,
                dob=dob,
                phone="+1-555-%04d" % random.randint(1000, 9999),
                blood_group=random.choice(BLOODS),
                address=random.choice(cities),
                allergies=random.choice(["", "", "", "Penicillin", "Peanuts", "Latex", "Sulfa drugs"]),
                emergency_contact="Family member",
                emergency_phone="+1-555-%04d" % random.randint(1000, 9999),
            ),
            sysu,
        )
        conn.execute("UPDATE patients SET created_at=? WHERE id=?", (day(-random.randint(0, 90)), cid))
    p1 = one(conn, "SELECT id, name FROM patients WHERE id=1")
    if p1:
        conn.execute(
            "INSERT INTO users(username,password_hash,full_name,role,patient_id) VALUES(?,?,?,?,?)",
            ("patient", hash_pw("patient123"), p1["name"], "Patient", p1["id"]),
        )

    doc_ids = [r["id"] for r in rows(conn, "SELECT id FROM staff WHERE role='Doctor'")]
    reasons = ["Routine check-up", "Chest pain", "Headache", "Fever", "Back pain", "Follow-up", "Vaccination", "Skin rash", "Prenatal visit", "Knee pain"]
    for i in range(110):
        off = random.randint(-14, 7)
        st = "Scheduled" if off >= 0 else random.choices(["Completed", "Cancelled", "No-show"], [8, 1, 1])[0]
        create(
            conn,
            "appointments",
            dict(
                patient_id=random.randint(1, 45),
                doctor_id=random.choice(doc_ids),
                date=day(off),
                time="%02d:%02d" % (random.randint(8, 16), random.choice([0, 15, 30, 45])),
                reason=random.choice(reasons),
                status=st,
            ),
            sysu,
        )

    dx = ["Hypertension", "Type 2 Diabetes", "Viral fever", "Migraine", "Lower back strain", "Acute bronchitis", "Gastritis", "Allergic rhinitis", "Anemia", "Osteoarthritis"]
    for i in range(40):
        create(
            conn,
            "encounters",
            dict(
                patient_id=random.randint(1, 45),
                doctor_id=random.choice(doc_ids),
                date=day(-random.randint(0, 20)),
                bp=f"{random.randint(105, 150)}/{random.randint(65, 95)}",
                temperature=f"{random.uniform(36.2, 39.2):.1f}",
                pulse=str(random.randint(60, 105)),
                weight=str(random.randint(45, 105)),
                diagnosis=random.choice(dx),
                notes="Patient examined; advised lifestyle modification and follow-up.",
                prescription="Tab Paracetamol 500mg TID x 3 days\nPlenty of fluids",
            ),
            sysu,
        )

    beds = [r["id"] for r in rows(conn, "SELECT id FROM beds ORDER BY RANDOM() LIMIT 14")]
    for i, b in enumerate(beds[:10]):
        create(
            conn,
            "admissions",
            dict(
                patient_id=random.randint(1, 45),
                doctor_id=random.choice(doc_ids),
                bed_id=b,
                admit_date=day(-random.randint(1, 9)),
                diagnosis=random.choice(["Pneumonia", "Post-operative care", "Cardiac monitoring", "Dengue fever", "Fracture management", "Diabetic ketoacidosis"]),
            ),
            sysu,
        )
    for a in rows(conn, "SELECT id FROM admissions LIMIT 4"):
        discharge(conn, a["id"], sysu)

    for i in range(35):
        o = create(conn, "lab_orders", dict(patient_id=random.randint(1, 45), doctor_id=random.choice(doc_ids), test_id=random.randint(1, 12)), sysu)
        stt = random.choice(["Ordered", "Sample Collected", "Completed", "Completed", "Completed"])
        conn.execute(
            "UPDATE lab_orders SET status=?, result=?, ordered_at=? WHERE id=?",
            (
                stt,
                "Within normal limits" if stt == "Completed" and random.random() > 0.3 else ("Abnormal – see physician" if stt == "Completed" else None),
                day(-random.randint(0, 14)),
                o,
            ),
        )
    for i in range(40):
        create(conn, "dispensing", dict(patient_id=random.randint(1, 45), medicine_id=random.randint(1, 15), quantity=random.randint(1, 10)), sysu)

    for inv in rows(conn, "SELECT * FROM invoices"):
        if random.random() < 0.75:
            full = random.random() < 0.6
            amt = inv["total"] if full else round(inv["total"] * random.choice([0.3, 0.5]), 2)
            if amt > 0:
                conn.execute(
                    "INSERT INTO payments(invoice_id,amount,method,date) VALUES(?,?,?,?)",
                    (inv["id"], amt, random.choice(["Cash", "Card", "Insurance", "UPI"]), day(-random.randint(0, 13))),
                )
                recompute(conn, inv["id"])
    conn.execute("UPDATE invoices SET date=COALESCE((SELECT MIN(date) FROM payments WHERE invoice_id=invoices.id), date)")
    conn.commit()


def init_db(target_db=None):
    if target_db:
        db_mod.ACTIVE_DB = target_db
    # Skip SQLite file migration and schema init when using PostgreSQL
    if getattr(db_mod, "USE_POSTGRES", False):
        conn = connect()
        # Tables already created via migration; just ensure we can query
        return
    # Automatically migrate root hospital.db into database/hospital.db if needed
    if db_mod.ACTIVE_DB == DB_PATH and not os.path.exists(DB_PATH) and os.path.exists(LEGACY_DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        shutil.copy2(LEGACY_DB_PATH, DB_PATH)
    fresh = not os.path.exists(db_mod.ACTIVE_DB)
    conn = connect(db_mod.ACTIVE_DB)
    conn.executescript(SCHEMA)
    cols = [r["name"] for r in rows(conn, "PRAGMA table_info(users)")]
    if "patient_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN patient_id INTEGER")
    if fresh or scalar(conn, "SELECT COUNT(*) FROM users") == 0:
        seed(conn)
        print("Seeded demo data.")
    elif not one(conn, "SELECT id FROM users WHERE username='patient'"):
        p1 = one(conn, "SELECT id, name FROM patients ORDER BY id LIMIT 1")
        if p1:
            conn.execute(
                "INSERT INTO users(username,password_hash,full_name,role,patient_id) VALUES(?,?,?,?,?)",
                ("patient", hash_pw("patient123"), p1["name"], "Patient", p1["id"]),
            )
            conn.commit()
    conn.close()
