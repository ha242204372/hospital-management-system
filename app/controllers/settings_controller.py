"""Hospital Settings & Master Data Onboarding Controller (Multi-Hospital / White-Label Setup)."""
from app.config import ApiError, ROLES
from app.models.db import rows, one, scalar, audit, get_settings, save_settings
from app.controllers.auth_controller import hash_pw

HOSPITAL_PRESETS = [
    {
        "id": "medicare",
        "hospital_name": "MediCare General Hospital",
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
        "invoice_footer": "Thank you for choosing MediCare General Hospital. Wishing you good health.",
        "default_theme": "indigo",
    },
    {
        "id": "alshifa",
        "hospital_name": "Al-Shifa International Hospital",
        "tagline": "Tertiary Care & Multi-Specialty Medical Center",
        "logo_icon": "🏥",
        "currency": "PKR",
        "address": "Sector H-8/4, Pitras Bukhari Road, Islamabad, Pakistan",
        "phone": "+92-51-846-3000",
        "emergency_phone": "+92-51-846-4646",
        "email": "care@alshifa-international.pk",
        "website": "www.alshifa-international.pk",
        "tax_id": "NTN-4109283-1",
        "mrn_prefix": "ASH",
        "invoice_prefix": "ASH-INV",
        "invoice_footer": "Al-Shifa International Hospital — Committed to Clinical Excellence.",
        "default_theme": "emerald",
    },
    {
        "id": "citycare",
        "hospital_name": "City Care & Trauma Center",
        "tagline": "24/7 Emergency, Cardiology, Surgery & Diagnostics",
        "logo_icon": "⚕",
        "currency": "PKR",
        "address": "Shahrah-e-Faisal, Block 6 PECHS, Karachi, Pakistan",
        "phone": "+92-21-3452-8800",
        "emergency_phone": "1020 / +92-21-3452-8899",
        "email": "admin@citycarekarachi.pk",
        "website": "www.citycarekarachi.pk",
        "tax_id": "NTN-7721904-9",
        "mrn_prefix": "CCK",
        "invoice_prefix": "CCK-BILL",
        "invoice_footer": "City Care & Trauma Center · 24-Hour Emergency & Pharmacy Services.",
        "default_theme": "sapphire",
    },
    {
        "id": "children_maternity",
        "hospital_name": "Noor Mother & Child Specialist Hospital",
        "tagline": "Obstetrics, Gynecology, Neonatology & Pediatric Care",
        "logo_icon": "🤱",
        "currency": "PKR",
        "address": "University Road, Hayatabad Phase 3, Peshawar, Pakistan",
        "phone": "+92-91-582-4400",
        "emergency_phone": "+92-91-582-4499",
        "email": "info@noorhospital.pk",
        "website": "www.noorhospital.pk",
        "tax_id": "NTN-5591023-4",
        "mrn_prefix": "NMC",
        "invoice_prefix": "NMC-INV",
        "invoice_footer": "Noor Mother & Child Specialist Hospital — Caring for Every Generation.",
        "default_theme": "crimson",
    },
]


def get_public_config(conn):
    s = get_settings(conn)
    return {
        "hospital_name": s["hospital_name"],
        "tagline": s["tagline"],
        "logo_icon": s["logo_icon"],
        "currency": s["currency"],
        "default_theme": s["default_theme"],
        "phone": s["phone"],
        "address": s["address"],
    }


def get_hospital_setup(conn, user):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can access Hospital Setup & Master Data")
    settings = get_settings(conn)
    departments = rows(
        conn,
        "SELECT d.*, (SELECT COUNT(*) FROM staff s WHERE s.department_id=d.id) staff_count FROM departments d ORDER BY d.name",
    )
    staff = rows(
        conn,
        "SELECT s.*, d.name department, (SELECT username FROM users u WHERE u.staff_id=s.id OR u.full_name=s.name LIMIT 1) login_user "
        "FROM staff s LEFT JOIN departments d ON d.id=s.department_id ORDER BY s.role='Doctor' DESC, s.name",
    )
    wards = rows(
        conn,
        "SELECT w.*, COUNT(b.id) total_beds, SUM(CASE WHEN b.status='Available' THEN 1 ELSE 0 END) available_beds "
        "FROM wards w LEFT JOIN beds b ON b.ward_id=w.id GROUP BY w.id ORDER BY w.name",
    )
    lab_tests = rows(conn, "SELECT * FROM lab_tests ORDER BY category, name")
    medicines = rows(conn, "SELECT * FROM medicines ORDER BY name")
    return {
        "settings": settings,
        "presets": HOSPITAL_PRESETS,
        "master": {
            "departments": departments,
            "staff": staff,
            "wards": wards,
            "lab_tests": lab_tests,
            "medicines": medicines,
        },
        "counts": {
            "departments": len(departments),
            "doctors": sum(1 for s in staff if s["role"] == "Doctor"),
            "staff_total": len(staff),
            "wards": len(wards),
            "beds": scalar(conn, "SELECT COUNT(*) FROM beds"),
            "lab_tests": len(lab_tests),
            "medicines": len(medicines),
            "patients": scalar(conn, "SELECT COUNT(*) FROM patients"),
        },
    }


def update_hospital_settings(conn, user, body):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can modify hospital settings")
    if not (body.get("hospital_name") or "").strip():
        raise ApiError(400, "Hospital Name is required")
    updated = save_settings(conn, body)
    audit(conn, user, "update_settings", f"hospital_name={updated['hospital_name']} ({updated['currency']})")
    return {"ok": True, "settings": updated}


def quick_add_doctor(conn, user, body):
    """Adds a Doctor or Staff member to master data and optionally creates their login user account."""
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can add staff master data")
    name = (body.get("name") or "").strip()
    role = (body.get("role") or "Doctor").strip()
    if not name:
        raise ApiError(400, "Full name is required")
    if role not in ROLES:
        raise ApiError(400, "Invalid staff role")

    dept_id = body.get("department_id")
    new_dept = (body.get("new_department") or "").strip()
    if new_dept:
        existing = one(conn, "SELECT id FROM departments WHERE LOWER(name)=LOWER(?)", (new_dept,))
        if existing:
            dept_id = existing["id"]
        else:
            cur_d = conn.execute("INSERT INTO departments(name,description) VALUES(?,?)", (new_dept, f"{new_dept} department"))
            dept_id = cur_d.lastrowid
    elif dept_id:
        dept_id = int(dept_id)
    else:
        dept_id = None

    try:
        fee = float(body.get("fee") or 0)
    except ValueError:
        fee = 0.0

    cur = conn.execute(
        "INSERT INTO staff(name,role,department_id,specialization,phone,email,fee,status) VALUES(?,?,?,?,?,?,?,?)",
        (
            name,
            role,
            dept_id,
            (body.get("specialization") or "").strip() or None,
            (body.get("phone") or "").strip() or None,
            (body.get("email") or "").strip() or None,
            fee,
            "Active",
        ),
    )
    staff_id = cur.lastrowid

    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if username and password:
        if one(conn, "SELECT id FROM users WHERE username=?", (username,)):
            raise ApiError(409, f"Username '{username}' already exists")
        conn.execute(
            "INSERT INTO users(username,password_hash,full_name,role,staff_id) VALUES(?,?,?,?,?)",
            (username, hash_pw(password), name, role, staff_id),
        )

    audit(conn, user, "quick_add_staff", f"{role}: {name} (fee={fee})")
    return {"ok": True, "id": staff_id}


def create_ward_with_beds(conn, user, body):
    """Creates a ward and automatically generates N numbered beds in one operation."""
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can configure wards & beds")
    name = (body.get("name") or "").strip()
    wtype = (body.get("type") or "General").strip()
    if not name:
        raise ApiError(400, "Ward name is required")
    try:
        rate = float(body.get("daily_rate") or 0)
        bed_count = int(body.get("bed_count") or 0)
    except ValueError:
        raise ApiError(400, "Invalid rate or bed count")
    if bed_count < 0 or bed_count > 100:
        raise ApiError(400, "Bed count must be between 0 and 100")

    prefix = (body.get("bed_prefix") or name[:2].upper()).strip().rstrip("-")
    cur = conn.execute("INSERT INTO wards(name,type,daily_rate) VALUES(?,?,?)", (name, wtype, rate))
    ward_id = cur.lastrowid
    for i in range(1, bed_count + 1):
        conn.execute("INSERT INTO beds(ward_id,bed_no,status) VALUES(?,?,?)", (ward_id, f"{prefix}-{i:02d}", "Available"))
    audit(conn, user, "create_ward_with_beds", f"{name} ({bed_count} beds, rate {rate})")
    return {"ok": True, "ward_id": ward_id, "beds_created": bed_count}


def clean_slate_for_new_hospital(conn, user, body=None):
    """Clears demo patient/clinical/billing records while keeping all Master Data intact for a new hospital go-live."""
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can initialize a clean-slate hospital database")
    body = body or {}
    if body.get("hospital_name"):
        save_settings(conn, body)

    # Clear transactional tables in foreign-key safe order
    for tbl in (
        "payments",
        "invoice_items",
        "invoices",
        "dispensing",
        "lab_orders",
        "admissions",
        "encounters",
        "appointments",
        "patients",
    ):
        conn.execute(f"DELETE FROM {tbl}")
    conn.execute("DELETE FROM users WHERE role='Patient'")
    conn.execute("UPDATE beds SET status='Available'")
    audit(conn, user, "clean_slate_go_live", "Cleared demo patients & transactions; preserved master data")
    return {"ok": True, "settings": get_settings(conn)}
