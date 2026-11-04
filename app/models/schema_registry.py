"""Resource metadata registry (RES) and foreign-key reference queries (REFS)."""
from app.config import ROLES, ALL, GENDERS, BLOODS


def F(name, label, type="text", **kw):
    d = dict(name=name, label=label, type=type)
    d.update(kw)
    return d


RES = {
    "patients": dict(
        label="Patients", icon="🧑‍🤝‍🧑", group="Front Desk", table="patients",
        fields=[F("name", "Full name", required=True), F("gender", "Gender", "select", options=GENDERS), F("dob", "Date of birth", "date"),
                F("phone", "Phone"), F("email", "Email"), F("blood_group", "Blood group", "select", options=BLOODS),
                F("allergies", "Allergies"), F("address", "Address", "textarea"),
                F("emergency_contact", "Emergency contact"), F("emergency_phone", "Emergency phone")],
        columns=[("mrn", "MRN"), ("name", "Name"), ("gender", "Gender"), ("age", "Age"), ("phone", "Phone"), ("blood_group", "Blood"), ("allergies", "Allergies")],
        sql="SELECT p.*, CASE WHEN dob IS NULL OR dob='' THEN NULL ELSE CAST((CURRENT_DATE - dob::date)/365.25 AS INT) END age FROM patients p ORDER BY id DESC" if __import__('app.models.db', fromlist=['USE_POSTGRES']).USE_POSTGRES else "SELECT p.*, CASE WHEN dob IS NULL OR dob='' THEN NULL ELSE CAST((julianday('now')-julianday(dob))/365.25 AS INT) END age FROM patients p ORDER BY id DESC",
        read=ALL, write=["Admin", "Receptionist", "Doctor", "Nurse"], delete=["Admin"], profile=True),
    "appointments": dict(
        label="Appointments", icon="📅", group="Front Desk", table="appointments",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("doctor_id", "Doctor", "ref", ref="doctors", required=True),
                F("date", "Date", "date", required=True), F("time", "Time", "time"), F("reason", "Reason"),
                F("visit_type", "Visit type", "select", options=["In-person", "Telemedicine"], default="In-person"),
                F("status", "Status", "select", options=["Scheduled", "Completed", "Cancelled", "No-show"], default="Scheduled")],
        columns=[("date", "Date"), ("time", "Time"), ("patient", "Patient"), ("doctor", "Doctor"), ("department", "Department"), ("reason", "Reason"), ("status", "Status")],
        sql="SELECT a.*, p.name patient, d.name doctor, dp.name department FROM appointments a JOIN patients p ON p.id=a.patient_id "
            "JOIN staff d ON d.id=a.doctor_id LEFT JOIN departments dp ON dp.id=d.department_id ORDER BY a.date DESC, a.time DESC",
        read=ALL, write=["Admin", "Receptionist", "Doctor", "Nurse", "Patient"], delete=["Admin", "Receptionist"]),
    "encounters": dict(
        label="Consultations (EMR)", icon="🩺", group="Clinical", table="encounters",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("doctor_id", "Doctor", "ref", ref="doctors", required=True),
                F("date", "Date", "date", required=True), F("bp", "Blood pressure"), F("temperature", "Temp (°C)"), F("pulse", "Pulse (bpm)"),
                F("weight", "Weight (kg)"), F("diagnosis", "Diagnosis", required=True), F("notes", "Clinical notes", "textarea"),
                F("prescription", "Prescription", "textarea")],
        columns=[("date", "Date"), ("patient", "Patient"), ("doctor", "Doctor"), ("bp", "BP"), ("pulse", "Pulse"), ("diagnosis", "Diagnosis")],
        sql="SELECT e.*, p.name patient, d.name doctor FROM encounters e JOIN patients p ON p.id=e.patient_id JOIN staff d ON d.id=e.doctor_id ORDER BY e.date DESC, e.id DESC",
        read=["Admin", "Doctor", "Nurse", "Patient"], write=["Admin", "Doctor", "Nurse"], delete=["Admin"]),
    "prescriptions": dict(
        label="Prescriptions", icon="💊", group="Clinical", table="prescriptions",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True),
                F("doctor_id", "Doctor", "ref", ref="doctors", required=True),
                F("medicine", "Medicine / Drug", required=True),
                F("dosage", "Dosage", required=True),
                F("frequency", "Frequency", required=True),
                F("duration", "Duration"),
                F("instructions", "Instructions", "textarea"),
                F("date", "Date", "date")],
        columns=[("date", "Date"), ("patient", "Patient"), ("doctor", "Doctor"), ("medicine", "Medicine"), ("dosage", "Dosage"), ("frequency", "Frequency"), ("duration", "Duration")],
        sql="SELECT r.*, p.name patient, d.name doctor FROM prescriptions r JOIN patients p ON p.id=r.patient_id LEFT JOIN staff d ON d.id=r.doctor_id ORDER BY r.id DESC",
        read=["Admin", "Doctor", "Nurse", "Pharmacist", "Patient"], write=["Admin", "Doctor"], delete=["Admin"]),
    "mar": dict(
        label="Medication Admin (MAR)", icon="💉", group="Clinical", table="mar",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True),
                F("medicine", "Medicine", required=True),
                F("dose", "Dose", required=True),
                F("route", "Route", "select", options=["Oral", "IV", "IM", "SC", "Topical", "Inhaled"], default="Oral"),
                F("scheduled_time", "Scheduled time"),
                F("given_time", "Given time"),
                F("status", "Status", "select", options=["Scheduled", "Given", "Held", "Refused"], default="Scheduled"),
                F("notes", "Notes", "textarea")],
        columns=[("scheduled_time", "Scheduled"), ("patient", "Patient"), ("medicine", "Medicine"), ("dose", "Dose"), ("route", "Route"), ("status", "Status"), ("given_time", "Given")],
        sql="SELECT m.*, p.name patient FROM mar m JOIN patients p ON p.id=m.patient_id ORDER BY m.id DESC",
        read=["Admin", "Doctor", "Nurse"], write=["Admin", "Nurse", "Doctor"], delete=["Admin"]),
    "admissions": dict(
        label="Admissions (IPD)", icon="🛏️", group="Clinical", table="admissions",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("doctor_id", "Attending doctor", "ref", ref="doctors", required=True),
                F("bed_id", "Bed", "ref", ref="beds_available", required=True), F("admit_date", "Admit date", "date", required=True),
                F("diagnosis", "Diagnosis / reason")],
        columns=[("admit_date", "Admitted"), ("patient", "Patient"), ("doctor", "Doctor"), ("ward", "Ward"), ("bed_no", "Bed"), ("diagnosis", "Diagnosis"), ("discharge_date", "Discharged"), ("status", "Status")],
        sql="SELECT a.*, p.name patient, d.name doctor, w.name ward, b.bed_no FROM admissions a JOIN patients p ON p.id=a.patient_id JOIN staff d ON d.id=a.doctor_id "
            "JOIN beds b ON b.id=a.bed_id JOIN wards w ON w.id=b.ward_id ORDER BY (a.status='Admitted') DESC, a.admit_date DESC",
        read=["Admin", "Doctor", "Nurse", "Receptionist", "Patient"], write=["Admin", "Doctor", "Nurse", "Receptionist"], delete=["Admin"],
        actions=[dict(key="discharge", label="Discharge", when=dict(status="Admitted")), dict(key="summary", label="Summary", when=dict(status="Discharged"))], no_edit_when=dict(status="Discharged")),
    "wards": dict(
        label="Wards & Beds", icon="🏥", group="Clinical", table="wards",
        fields=[F("name", "Ward name", required=True), F("type", "Type", "select", options=["General", "Private", "ICU", "Emergency", "Maternity", "Pediatric"]),
                F("daily_rate", "Daily rate (PKR)", "number")],
        columns=[("name", "Ward"), ("type", "Type"), ("daily_rate", "Daily rate (PKR)"), ("total_beds", "Beds"), ("occupied", "Occupied")],
        sql="SELECT w.*, (SELECT COUNT(*) FROM beds WHERE ward_id=w.id) total_beds, (SELECT COUNT(*) FROM beds WHERE ward_id=w.id AND status='Occupied') occupied FROM wards w ORDER BY w.id",
        read=["Admin", "Doctor", "Nurse", "Receptionist"], write=["Admin", "Nurse"], delete=["Admin"]),
    "beds": dict(
        label="Beds", icon="🛌", group="Clinical", table="beds",
        fields=[F("ward_id", "Ward", "ref", ref="wards", required=True), F("bed_no", "Bed number", required=True),
                F("status", "Status", "select", options=["Available", "Occupied", "Maintenance"], default="Available")],
        columns=[("ward", "Ward"), ("bed_no", "Bed"), ("status", "Status"), ("occupant", "Current Patient")],
        sql="SELECT b.*, w.name ward, (SELECT p.name FROM admissions a JOIN patients p ON p.id=a.patient_id WHERE a.bed_id=b.id AND a.status='Admitted' LIMIT 1) occupant FROM beds b JOIN wards w ON w.id=b.ward_id ORDER BY w.id, b.bed_no",
        read=["Admin", "Doctor", "Nurse", "Receptionist"], write=["Admin", "Nurse"], delete=["Admin"]),
    "lab_orders": dict(
        label="Lab Orders", icon="🔬", group="Diagnostics", table="lab_orders",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("doctor_id", "Ordering doctor", "ref", ref="doctors"),
                F("test_id", "Test", "ref", ref="lab_tests", required=True),
                F("status", "Status", "select", options=["Ordered", "Sample Collected", "Completed"], default="Ordered"),
                F("result", "Result", "textarea"), F("notes", "Notes")],
        columns=[("ordered_at", "Ordered"), ("patient", "Patient"), ("test", "Test"), ("doctor", "Doctor"), ("status", "Status"), ("result", "Result")],
        sql="SELECT o.*, p.name patient, t.name test, d.name doctor FROM lab_orders o JOIN patients p ON p.id=o.patient_id JOIN lab_tests t ON t.id=o.test_id "
            "LEFT JOIN staff d ON d.id=o.doctor_id ORDER BY o.id DESC",
        read=["Admin", "Doctor", "Nurse", "Lab Technician", "Patient"], write=["Admin", "Doctor", "Lab Technician", "Nurse"], delete=["Admin"]),
    "lab_tests": dict(
        label="Lab Test Catalog", icon="🧪", group="Diagnostics", table="lab_tests",
        fields=[F("name", "Test name", required=True), F("category", "Category", "select", options=["Hematology", "Biochemistry", "Microbiology", "Radiology", "Pathology", "Other"]),
                F("price", "Price (PKR)", "number", required=True), F("reference_range", "Reference range")],
        columns=[("name", "Test"), ("category", "Category"), ("price", "Price (PKR)"), ("reference_range", "Reference range")],
        sql="SELECT * FROM lab_tests ORDER BY name",
        read=["Admin", "Doctor", "Nurse", "Lab Technician", "Accountant"], write=["Admin", "Lab Technician"], delete=["Admin"]),
    "medicines": dict(
        label="Pharmacy Inventory", icon="💊", group="Pharmacy", table="medicines",
        fields=[F("name", "Medicine", required=True), F("category", "Category"), F("stock", "Stock", "number", required=True),
                F("reorder_level", "Reorder level", "number"), F("unit_price", "Unit price (PKR)", "number", required=True),
                F("expiry_date", "Expiry date", "date"), F("supplier", "Supplier")],
        columns=[("name", "Medicine"), ("category", "Category"), ("stock", "Stock"), ("reorder_level", "Reorder at"), ("unit_price", "Unit price (PKR)"), ("expiry_date", "Expiry"), ("supplier", "Supplier")],
        sql="SELECT * FROM medicines ORDER BY name",
        read=["Admin", "Doctor", "Nurse", "Pharmacist"], write=["Admin", "Pharmacist"], delete=["Admin", "Pharmacist"], flag="stock"),
    "dispensing": dict(
        label="Dispensing", icon="🧾", group="Pharmacy", table="dispensing",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("medicine_id", "Medicine", "ref", ref="medicines", required=True),
                F("quantity", "Quantity", "number", required=True)],
        columns=[("date", "Date"), ("patient", "Patient"), ("medicine", "Medicine"), ("quantity", "Qty"), ("amount", "Amount (PKR)")],
        sql="SELECT s.*, p.name patient, m.name medicine FROM dispensing s JOIN patients p ON p.id=s.patient_id JOIN medicines m ON m.id=s.medicine_id ORDER BY s.id DESC",
        read=["Admin", "Pharmacist", "Doctor", "Nurse", "Patient"], write=["Admin", "Pharmacist"], delete=[], no_edit=True),
    "invoices": dict(
        label="Billing & Invoices", icon="💳", group="Finance", table="invoices",
        fields=[F("patient_id", "Patient", "ref", ref="patients", required=True), F("date", "Date", "date"), F("notes", "Notes")],
        columns=[("number", "Invoice"), ("date", "Date"), ("patient", "Patient"), ("total", "Total (PKR)"), ("paid", "Paid (PKR)"), ("balance", "Balance (PKR)"), ("status", "Status")],
        sql="SELECT i.*, p.name patient, (i.total-i.paid) balance FROM invoices i JOIN patients p ON p.id=i.patient_id ORDER BY i.id DESC",
        read=["Admin", "Receptionist", "Accountant", "Patient"], write=["Admin", "Receptionist", "Accountant"], delete=["Admin"], invoice=True),
    "expenses": dict(
        label="Expenses", icon="💸", group="Finance", table="expenses",
        fields=[F("date", "Date", "date", required=True), F("category", "Category", required=True),
                F("vendor", "Vendor"), F("description", "Description", "textarea"),
                F("amount", "Amount (PKR)", "number", required=True), F("paid", "Paid (PKR)", "number"),
                F("status", "Status", "select", options=["Unpaid", "Partial", "Paid"], default="Unpaid"),
                F("method", "Payment method", "select", options=["Cash", "Bank Transfer", "Card", "Cheque"]),
                F("notes", "Notes", "textarea")],
        columns=[("date", "Date"), ("category", "Category"), ("vendor", "Vendor"), ("amount", "Amount"), ("paid", "Paid"), ("status", "Status")],
        sql="SELECT * FROM expenses ORDER BY date DESC, id DESC",
        read=["Admin", "Accountant"], write=["Admin", "Accountant"], delete=["Admin"]),
    "assets": dict(
        label="Assets", icon="🏢", group="Finance", table="assets",
        fields=[F("name", "Asset name", required=True), F("category", "Category"),
                F("purchase_date", "Purchase date", "date"), F("cost", "Cost (PKR)", "number"),
                F("residual_value", "Residual value (PKR)", "number"),
                F("status", "Status", "select", options=["Active", "Maintenance", "Retired"], default="Active")],
        columns=[("name", "Name"), ("category", "Category"), ("purchase_date", "Purchased"), ("cost", "Cost"), ("status", "Status")],
        sql="SELECT * FROM assets ORDER BY id DESC",
        read=["Admin", "Accountant"], write=["Admin", "Accountant"], delete=["Admin"]),
    "departments": dict(
        label="Departments", icon="🏢", group="Administration", table="departments",
        fields=[F("name", "Department", required=True), F("description", "Description", "textarea")],
        columns=[("name", "Department"), ("description", "Description"), ("doctors", "Doctors")],
        sql="SELECT d.*, (SELECT COUNT(*) FROM staff s WHERE s.department_id=d.id AND s.role='Doctor') doctors FROM departments d ORDER BY name",
        read=ALL, write=["Admin"], delete=["Admin"]),
    "staff": dict(
        label="Staff & Doctors", icon="👩‍⚕️", group="Administration", table="staff",
        fields=[F("name", "Name", required=True), F("role", "Role", "select", options=ROLES, required=True),
                F("department_id", "Department", "ref", ref="departments"), F("specialization", "Specialization"),
                F("phone", "Phone"), F("email", "Email"), F("fee", "Consultation fee (PKR)", "number"),
                F("status", "Status", "select", options=["Active", "On leave", "Inactive"], default="Active")],
        columns=[("name", "Name"), ("role", "Role"), ("department", "Department"), ("specialization", "Specialization"), ("phone", "Phone"), ("fee", "Fee (PKR)"), ("status", "Status")],
        sql="SELECT s.*, d.name department FROM staff s LEFT JOIN departments d ON d.id=s.department_id ORDER BY s.role, s.name",
        read=ALL, write=["Admin"], delete=["Admin"]),
    "users": dict(
        label="User Accounts", icon="🔐", group="Administration", table="users",
        fields=[F("username", "Username", required=True), F("full_name", "Full name", required=True), F("role", "Role", "select", options=ROLES, required=True),
                F("password", "Password (blank = unchanged)", "password")],
        columns=[("username", "Username"), ("full_name", "Name"), ("role", "Role")],
        sql="SELECT id, username, full_name, role FROM users ORDER BY id",
        read=["Admin"], write=["Admin"], delete=["Admin"]),
    "audit_log": dict(
        label="Audit Log", icon="📜", group="Administration", table="audit_log", fields=[],
        columns=[("at", "Time"), ("user", "User"), ("action", "Action"), ("detail", "Detail")],
        sql="SELECT * FROM audit_log ORDER BY id DESC LIMIT 500", read=["Admin"], write=[], delete=[]),
}

REFS = {
    "patients": "SELECT id, mrn||' · '||name label FROM patients ORDER BY name",
    "doctors": "SELECT s.id, s.name||COALESCE(' ('||d.name||')','') label FROM staff s LEFT JOIN departments d ON d.id=s.department_id WHERE s.role='Doctor' AND s.status='Active' ORDER BY s.name",
    "departments": "SELECT id, name label FROM departments ORDER BY name",
    "wards": "SELECT id, name label FROM wards ORDER BY name",
    "beds_available": "SELECT b.id, w.name||' · Bed '||b.bed_no||' (PKR '||CAST(w.daily_rate AS INT)||'/day)' label FROM beds b JOIN wards w ON w.id=b.ward_id WHERE b.status='Available' ORDER BY w.name, b.bed_no",
    "lab_tests": "SELECT id, name||' (PKR '||CAST(price AS INT)||')' label FROM lab_tests ORDER BY name",
    "medicines": "SELECT id, name||' — stock '||stock||' @ PKR '||unit_price label FROM medicines ORDER BY name",
}
