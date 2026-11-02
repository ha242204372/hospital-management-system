"""End-to-end smoke test: exercises all HMS modules, workflows, and role-based access controls."""
import os, sys, json, io, tempfile
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server

server.DB = os.path.join(tempfile.mkdtemp(), "t.db")
server.init_db()


class DummyHandler(server.Handler):
    def __init__(self, method, path, body=None, cookie=None):
        self.path = path
        self.command = method
        raw = json.dumps(body).encode() if body is not None else b""
        self.headers = {"Content-Length": str(len(raw))}
        if cookie:
            self.headers["Cookie"] = cookie
        self.rfile = io.BytesIO(raw)
        self.wfile = io.BytesIO()
        self._status = 200
        self._headers = {}

    def send_response(self, code):
        self._status = code

    def send_header(self, k, v):
        self._headers[k] = v

    def end_headers(self):
        pass


def call(method, path, body=None, cookie=None):
    h = DummyHandler(method, path, body, cookie)
    h.dispatch(method)
    raw = h.wfile.getvalue()
    ctype = h._headers.get("Content-Type", "")
    parsed = json.loads(raw or b"{}") if ctype == "application/json" else raw
    return h._status, parsed, h._headers


def login(u, p):
    s, _, h = call("POST", "/api/login", {"username": u, "password": p})
    assert s == 200, (u, s)
    return h["Set-Cookie"].split(";")[0]


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


s, _, _ = call("POST", "/api/login", {"username": "admin", "password": "bad"})
ok(s == 401, "bad login rejected")
ok(call("GET", "/api/dashboard")[0] == 401, "unauthenticated blocked")
ok(call("GET", "/")[0] == 200 and call("GET", "/static/app.js")[0] == 200, "static files served")
A = login("admin", "admin123")
s, meta, _ = call("GET", "/api/meta", cookie=A)
ok(s == 200 and len(meta["resources"]) == 15, "admin sees all modules")
P = login("pharmacy", "pharmacy123")
ok(call("GET", "/api/r/invoices", cookie=P)[0] == 403, "pharmacist blocked from billing")
ok(call("GET", "/api/r/medicines", cookie=P)[0] == 200, "pharmacist can read inventory")

# patient -> appointment -> consultation -> billing
s, r, _ = call("POST", "/api/r/patients", {"name": "Test Patient", "gender": "Male", "dob": "1990-01-01"}, A)
pid = r["id"]
ok(s == 200, "create patient")
s, r, _ = call("POST", "/api/r/patients", {"gender": "Male"}, A)
ok(s == 400, "validation: name required")
call("POST", "/api/r/encounters", {"patient_id": pid, "doctor_id": 1, "diagnosis": "Flu"}, A)
inv = [i for i in call("GET", "/api/r/invoices", cookie=A)[1] if i["patient"] == "Test Patient"]
ok(len(inv) == 1 and inv[0]["total"] == 900, "consultation auto-billed with doctor fee")
# pharmacy dispense reduces stock and bills
before = [m for m in call("GET", "/api/r/medicines", cookie=P)[1] if m["id"] == 1][0]["stock"]
s, _, _ = call("POST", "/api/r/dispensing", {"patient_id": pid, "medicine_id": 1, "quantity": 4}, P)
after = [m for m in call("GET", "/api/r/medicines", cookie=P)[1] if m["id"] == 1][0]["stock"]
ok(s == 200 and before - after == 4, "dispense decrements stock")
s, _, _ = call("POST", "/api/r/dispensing", {"patient_id": pid, "medicine_id": 1, "quantity": 99999}, P)
ok(s == 400, "dispense blocked when insufficient stock")
# lab
call("POST", "/api/r/lab_orders", {"patient_id": pid, "test_id": 1}, A)
# admission + discharge
beds = call("GET", "/api/options/beds_available", cookie=A)[1]
s, r, _ = call("POST", "/api/r/admissions", {"patient_id": pid, "doctor_id": 1, "bed_id": beds[0]["id"], "admit_date": "2000-01-01"}, A)
ok(s == 200, "admit patient")
s, _, _ = call("POST", "/api/r/admissions", {"patient_id": pid, "doctor_id": 1, "bed_id": beds[0]["id"]}, A)
ok(s == 400, "occupied bed cannot be double-booked")
s, d, _ = call("POST", f"/api/admissions/{r['id']}/discharge", cookie=A)
ok(s == 200 and d["amount"] > 0, "discharge bills bed days")
# payment
inv = [i for i in call("GET", "/api/r/invoices", cookie=A)[1] if i["patient"] == "Test Patient"][0]
s, d, _ = call("POST", f"/api/invoices/{inv['id']}/payments", {"amount": inv["total"] + 1}, A)
ok(s == 400, "overpayment rejected")
s, d, _ = call("POST", f"/api/invoices/{inv['id']}/payments", {"amount": inv["total"], "method": "Card"}, A)
ok(s == 200 and d["status"] == "Paid", "full payment marks invoice Paid")
ok(call("GET", f"/api/patients/{pid}/profile", cookie=A)[0] == 200, "patient profile")
ok(call("GET", "/api/dashboard", cookie=A)[0] == 200 and call("GET", "/api/reports", cookie=A)[0] == 200, "dashboard + reports")
s, r, _ = call("POST", "/api/r/users", {"username": "x1", "full_name": "X", "role": "Nurse", "password": "pw"}, A)
ok(s == 200 and login("x1", "pw"), "admin creates user who can log in")
PAT = login("patient", "patient123")
s, p_appts, _ = call("GET", "/api/r/appointments", cookie=PAT)
ok(s == 200 and all(a["patient_id"] == 1 for a in p_appts), "patient role sees only own appointments")
ok(call("GET", "/api/patients/1/profile", cookie=PAT)[0] == 200, "patient can view own profile")
ok(call("GET", "/api/patients/2/profile", cookie=PAT)[0] == 403, "patient blocked from other patient profile")

# Gemini AI Hub endpoints
s, ai_st, _ = call("GET", "/api/ai/status", cookie=A)
ok(s == 200 and "available_models" in ai_st and ai_st["model"] in [m["id"] for m in ai_st["available_models"]], "Gemini AI status endpoint")
s, tr, _ = call("POST", "/api/ai/triage", {"symptoms": "Severe chest pain radiating to left arm and sweating", "age": 58, "gender": "Male"}, cookie=A)
ok(s == 200 and tr["recommended_department"] == "Cardiology" and tr["esi_level"] == 2 and len(tr.get("emergency_medications", [])) > 0, "Gemini AI symptom triage + emergency medications")
s, cp, _ = call("POST", "/api/ai/copilot", {"patient_id": pid, "notes": "Productive cough and fever 3 days", "bp": "124/80", "temperature": "38.2"}, cookie=A)
ok(s == 200 and "soap_notes" in cp and "prescription" in cp, "Gemini AI clinical SOAP copilot")
s, sm, _ = call("POST", "/api/ai/patient-summary", {"patient_id": pid}, cookie=A)
ok(s == 200 and "Clinical Overview" in sm["summary"], "Gemini AI longitudinal patient summary")
s, rx, _ = call("POST", "/api/ai/rx-check", {"patient_id": pid, "allergies": "Penicillin", "medicines": ["Amoxicillin 500mg", "Paracetamol 500mg"]}, cookie=A)
ok(s == 200 and "ALLERGY CONFLICT" in rx["report"], "Gemini AI pharmacy allergy/interaction check")
s, br, _ = call("POST", "/api/ai/briefing", {"question": "What is our bed occupancy?"}, cookie=A)
ok(s == 200 and "Bed" in br["reply"], "Gemini AI executive briefing & Q&A")

# Database Studio + Quick operational actions
s, dbi, _ = call("GET", "/api/db/info", cookie=A)
ok(s == 200 and len(dbi["tables"]) >= 15 and dbi["total_rows"] > 100, "Database Studio table & file inspector")
s, dbq, _ = call("POST", "/api/db/query", {"sql": "SELECT mrn, name FROM patients LIMIT 5"}, cookie=A)
ok(s == 200 and dbq["count"] == 5, "Database Studio read-only SQL console")
s, _, _ = call("POST", "/api/db/query", {"sql": "DROP TABLE patients"}, cookie=A)
ok(s == 400, "Database Studio blocks destructive SQL in console")
s, m_res, _ = call("POST", "/api/medicines/1/restock", {"quantity": 25}, cookie=P)
ok(s == 200 and m_res["stock"] > 25, "One-click pharmacy restock endpoint")

# Multi-Hospital Setup & Master Data Onboarding endpoints
s, pub, _ = call("GET", "/api/public-config")
ok(s == 200 and pub["currency"] == "PKR" and "hospital_name" in pub, "Public hospital branding config endpoint")
s, st_get, _ = call("GET", "/api/settings", cookie=A)
ok(s == 200 and len(st_get["presets"]) >= 4 and "master" in st_get, "Hospital Setup & Master Data overview")
s, st_upd, _ = call(
    "POST",
    "/api/settings",
    {"hospital_name": "Al-Shifa International Hospital", "currency": "PKR", "mrn_prefix": "ASH", "invoice_prefix": "ASH-INV"},
    cookie=A,
)
ok(s == 200 and st_upd["settings"]["hospital_name"] == "Al-Shifa International Hospital", "White-label hospital rebranding update")
s, new_pt, _ = call("POST", "/api/r/patients", {"name": "Zainab Bibi", "gender": "Female"}, cookie=A)
s, z_prof, _ = call("GET", f"/api/patients/{new_pt['id']}/profile", cookie=A)
ok(s == 200 and z_prof["mrn"].startswith("ASH"), "Custom hospital MRN prefix applied to new patients")
s, q_doc, _ = call(
    "POST",
    "/api/settings/doctor-quick-add",
    {"name": "Dr. Tariq Mahmood", "role": "Doctor", "new_department": "Oncology", "specialization": "Medical Oncologist", "fee": 2000, "username": "dr.tariq", "password": "pw123"},
    cookie=A,
)
ok(s == 200 and login("dr.tariq", "pw123"), "Quick-add Doctor with auto-created department and login account")
s, w_res, _ = call(
    "POST",
    "/api/settings/ward-with-beds",
    {"name": "Oncology Ward", "type": "Private", "daily_rate": 4500, "bed_prefix": "ONC", "bed_count": 5},
    cookie=A,
)
ok(s == 200 and w_res["beds_created"] == 5, "One-click Ward + Auto-Bed generator")
s, cs_res, _ = call("POST", "/api/settings/clean-slate", {"hospital_name": "Al-Shifa International Hospital"}, cookie=A)
s, after_setup, _ = call("GET", "/api/settings", cookie=A)
ok(s == 200 and after_setup["counts"]["patients"] == 0 and after_setup["counts"]["doctors"] >= 9, "Clean-slate Go-Live mode clears demo patients while keeping master data")
print("ALL TESTS PASSED")

