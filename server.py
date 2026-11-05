#!/usr/bin/env python3
"""VizMedCare HMS — Entry-Point HTTP Server & Router (MVC Architecture).

Directory Structure:
  app/
    config.py                      # Paths, constants, roles, ApiError
    models/
      db.py                        # SQLite connection, schema DDL, query & billing helpers
      schema_registry.py           # Resource definitions (RES) & lookup queries (REFS)
      seed.py                      # Demo seeding & automatic migration to database/hospital.db
    controllers/
      auth_controller.py           # Password hashing, login, logout, session store
      crud_controller.py           # Generic CRUD, validation, clinical & billing hooks
      analytics_controller.py      # Dashboard KPIs, 30-day Reports, 360° Patient Profile, Invoices
      ai_controller.py             # Gemini AI Hub routes (/api/ai/*)
      db_controller.py             # Database Studio routes (/api/db/*)
    views/
      templates/index.html         # SPA HTML shell
      static/css/style.css         # Multi-theme stylesheet (Royal Indigo default + 5 themes)
      static/js/app.js             # Frontend application & canvas charts
  database/
    hospital.db                    # SQLite relational database file
"""
import json
import mimetypes
import os
import re
import sqlite3
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import gemini_ai
from app.config import (
    DB_PATH,
    STATIC_DIR,
    TEMPLATES_DIR,
    VIEWS_DIR,
    HOSPITAL_NAME,
    ROLES,
    ApiError,
)
import app.models.db as db_mod
from app.models.db import connect, rows, one, today, audit, recompute, get_settings
from app.models.schema_registry import RES, REFS
from app.models.seed import seed, init_db as _init_db
from app.controllers.auth_controller import SESSIONS, current_user, handle_login, handle_logout
from app.controllers.crud_controller import get_res, create, update, delete, discharge
from app.controllers.analytics_controller import invoice_detail, patient_profile, dashboard, reports
from app.controllers.accounts_controller import balance_sheet, gl_summary, financial_kpis
from app.controllers.ai_controller import handle_ai_route
from app.controllers.db_controller import get_db_info, run_sql_query, reset_demo_db
from app.controllers.settings_controller import (
    get_public_config,
    get_hospital_setup,
    update_hospital_settings,
    quick_add_doctor,
    create_ward_with_beds,
    clean_slate_for_new_hospital,
)

# Default database location inside `database/hospital.db` (overridable for tests)
DB = DB_PATH


def init_db():
    db_mod.ACTIVE_DB = DB
    _init_db(DB)


class Handler(BaseHTTPRequestHandler):
    server_version = "VizMedCareHMS/2.0-MVC"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json", headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def current_user(self):
        return current_user(self.headers.get("Cookie", ""))

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            raise ApiError(400, "Invalid JSON")

    def do_GET(self):
        if urlparse(self.path).path == "/api/db/download":
            user = self.current_user()
            if not user or user["role"] != "Admin":
                return self._send(403, {"error": "Only Admin can download database backups"})
            db_mod.ACTIVE_DB = DB
            with open(DB, "rb") as f:
                data = f.read()
            return self._send(
                200,
                data,
                "application/x-sqlite3",
                {"Content-Disposition": 'attachment; filename="hospital-backup.db"'},
            )
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def static(self, path):
        if path in ("/", "", "/index.html"):
            candidates = [
                os.path.join(TEMPLATES_DIR, "index.html"),
                os.path.join(STATIC_DIR, "index.html"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "views", "templates", "index.html"),
            ]
            full = next((c for c in candidates if os.path.isfile(c)), candidates[0])
        else:
            rel = path.lstrip("/").replace("static/", "", 1)
            full = os.path.normpath(os.path.join(STATIC_DIR, rel))
            if not (full.startswith(STATIC_DIR) and os.path.isfile(full)):
                # Check MVC views/static fallback
                alt_map = {
                    "style.css": os.path.join(VIEWS_DIR, "static", "css", "style.css"),
                    "app.js": os.path.join(VIEWS_DIR, "static", "js", "app.js"),
                }
                full = alt_map.get(rel, full)
        if not os.path.isfile(full):
            return self._send(404, f"Not found: {path} -> {full}".encode(), "text/plain")
        with open(full, "rb") as f:
            self._send(200, f.read(), mimetypes.guess_type(full)[0] or "application/octet-stream")

    def dispatch(self, method):
        u = urlparse(self.path)
        path = u.path
        if not path.startswith("/api/"):
            return self.static(path) if method == "GET" else self._send(405, b"", "text/plain")
        db_mod.ACTIVE_DB = DB
        conn = connect(DB)
        try:
            out = self.api(conn, method, path, parse_qs(u.query))
            conn.commit()
            if isinstance(out, tuple):
                self._send(200, out[0], headers=out[1])
            else:
                self._send(200, out)
        except ApiError as e:
            conn.rollback()
            self._send(e.code, {"error": e.msg})
        except sqlite3.IntegrityError as e:
            conn.rollback()
            self._send(409, {"error": f"Data conflict: {e}"})
        except Exception as e:  # pragma: no cover
            conn.rollback()
            import traceback
            traceback.print_exc()
            self._send(500, {"error": "Server error: " + str(e)})
        finally:
            conn.close()

    def api(self, conn, method, path, qs):
        # 1. Public & Auth Controller routes
        if path == "/api/public-config" and method == "GET":
            return get_public_config(conn)
        if path == "/api/login" and method == "POST":
            return handle_login(conn, self.body())
        if path == "/api/logout":
            return handle_logout(self.headers.get("Cookie", ""))

        user = self.current_user()
        if not user:
            raise ApiError(401, "Not authenticated")
        role = user["role"]

        # 2. Metadata route
        if path == "/api/meta":
            settings = get_settings(conn)
            cur_code = settings.get("currency") or "PKR"
            res = []
            for k, r in RES.items():
                if role in r["read"]:
                    fields = [
                        {**f, "label": f["label"].replace("(PKR)", f"({cur_code})")}
                        for f in r["fields"]
                    ]
                    columns = [
                        (c[0], c[1].replace("(PKR)", f"({cur_code})"))
                        for c in r["columns"]
                    ]
                    res.append(
                        dict(
                            key=k,
                            label=r["label"],
                            icon=r["icon"],
                            group=r["group"],
                            fields=fields,
                            columns=columns,
                            canWrite=role in r["write"],
                            canDelete=role in r["delete"],
                            noEdit=bool(r.get("no_edit")),
                            actions=r.get("actions", []) if role in r["write"] else [],
                            profile=bool(r.get("profile")),
                            invoice=bool(r.get("invoice")),
                            flag=r.get("flag"),
                            noEditWhen=r.get("no_edit_when"),
                        )
                    )
            return {
                "user": user,
                "hospital": settings.get("hospital_name") or HOSPITAL_NAME,
                "settings": settings,
                "resources": res,
                "dashboard": role in ROLES,
                "reports": role in ("Admin", "Accountant"),
                "ai": gemini_ai.get_status(),
            }

        # 2b. Hospital Setup & Master Data routes
        if path == "/api/settings" and method == "GET":
            return get_hospital_setup(conn, user)
        if path == "/api/settings" and method == "POST":
            return update_hospital_settings(conn, user, self.body())
        if path == "/api/settings/doctor-quick-add" and method == "POST":
            return quick_add_doctor(conn, user, self.body())
        if path == "/api/settings/ward-with-beds" and method == "POST":
            return create_ward_with_beds(conn, user, self.body())
        if path == "/api/settings/clean-slate" and method == "POST":
            return clean_slate_for_new_hospital(conn, user, self.body())

        # 3. Gemini AI Hub Controller routes
        if path.startswith("/api/ai/"):
            ai_out = handle_ai_route(conn, method, path, user, self.body)
            if ai_out is not None:
                return ai_out

        # 4. Database Studio Controller routes
        if path == "/api/db/info" and method == "GET":
            return get_db_info(conn, user)
        if path == "/api/db/query" and method == "POST":
            return run_sql_query(conn, user, self.body())
        if path == "/api/db/reset" and method == "POST":
            return reset_demo_db(conn, user)

        # 5. Quick Operational Status routes
        m = re.fullmatch(r"/api/appointments/(\d+)/status", path)
        if m and method == "POST":
            get_res("appointments", user, "write")
            aid = int(m.group(1))
            st = (self.body().get("status") or "").strip()
            if st not in ("Scheduled", "Completed", "Cancelled", "No-show"):
                raise ApiError(400, "Invalid appointment status")
            conn.execute("UPDATE appointments SET status=? WHERE id=?", (st, aid))
            audit(conn, user, "appointment_status", f"appointment #{aid} -> {st}")
            return {"ok": True}

        m = re.fullmatch(r"/api/medicines/(\d+)/restock", path)
        if m and method == "POST":
            get_res("medicines", user, "write")
            mid = int(m.group(1))
            try:
                qty = int(self.body().get("quantity") or 0)
            except ValueError:
                raise ApiError(400, "Invalid quantity")
            if qty <= 0:
                raise ApiError(400, "Quantity must be positive")
            conn.execute("UPDATE medicines SET stock=stock+? WHERE id=?", (qty, mid))
            med = one(conn, "SELECT * FROM medicines WHERE id=?", (mid,))
            audit(conn, user, "restock", f"{med['name']} +{qty} (now {med['stock']})")
            return med

        m = re.fullmatch(r"/api/beds/(\d+)/status", path)
        if m and method == "POST":
            get_res("beds", user, "write")
            bid = int(m.group(1))
            st = (self.body().get("status") or "").strip()
            if st not in ("Available", "Maintenance"):
                raise ApiError(400, "Can only toggle between Available and Maintenance (use Admissions to occupy/discharge)")
            cur_b = one(conn, "SELECT * FROM beds WHERE id=?", (bid,))
            if not cur_b:
                raise ApiError(404, "Bed not found")
            if cur_b["status"] == "Occupied":
                raise ApiError(400, "Cannot change status of an Occupied bed — discharge the patient first")
            conn.execute("UPDATE beds SET status=? WHERE id=?", (st, bid))
            audit(conn, user, "bed_status", f"bed #{bid} -> {st}")
            return {"ok": True}

        # 6. Reference Options route
        m = re.fullmatch(r"/api/options/(\w+)", path)
        if m:
            if m.group(1) not in REFS:
                raise ApiError(404, "Unknown option set")
            cur_code = (get_settings(conn).get("currency") or "PKR").replace("'", "")
            sql_ref = REFS[m.group(1)].replace("PKR ", f"{cur_code} ")
            opts = rows(conn, sql_ref)
            if m.group(1) == "patients" and role == "Patient" and user.get("patient_id"):
                opts = [o for o in opts if o["id"] == user["patient_id"]]
            return opts

        # 7. Analytics & Profile Controller routes
        if path == "/api/dashboard":
            return dashboard(conn)
        if path == "/api/reports":
            if role not in ("Admin", "Accountant"):
                raise ApiError(403, "Not permitted")
            return reports(conn)
        if path == "/api/accounts/kpis":
            if role not in ("Admin", "Accountant"):
                raise ApiError(403, "Not permitted")
            return financial_kpis(conn)
        if path == "/api/accounts/balance-sheet":
            if role not in ("Admin", "Accountant"):
                raise ApiError(403, "Not permitted")
            return balance_sheet(conn)


        if path == "/api/queue/today":
            t = today()
            q = rows(conn, """SELECT a.id, a.date, a.time, a.reason, a.status, p.name patient, p.mrn, d.name doctor
                FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN staff d ON d.id=a.doctor_id
                WHERE a.date=? AND a.status='Scheduled' ORDER BY a.time""", (t,))
            upcoming = rows(conn, """SELECT a.date, a.time, p.name patient, d.name doctor, a.reason, a.status
                FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN staff d ON d.id=a.doctor_id
                WHERE a.date>? AND a.status='Scheduled' ORDER BY a.date, a.time LIMIT 15""", (t,))
            return {"date": t, "queue": q, "upcoming": upcoming}

        m = re.fullmatch(r"/api/patients/(\d+)/clinical-context", path)
        if m:
            pid = int(m.group(1))
            adm = rows(conn, "SELECT id, diagnosis, status, admit_date FROM admissions WHERE patient_id=? AND status='Admitted' ORDER BY id DESC LIMIT 1", (pid,))
            enc = rows(conn, "SELECT date, diagnosis, bp, pulse, temperature, notes FROM encounters WHERE patient_id=? ORDER BY date DESC LIMIT 5", (pid,))
            rx = rows(conn, "SELECT date, diagnosis, dosage, frequency FROM prescriptions WHERE patient_id=? ORDER BY id DESC LIMIT 5", (pid,))
            return {"indoor": bool(adm), "admission": adm[0] if adm else None, "encounters": enc, "prescriptions": rx}

        if path == "/api/rx/check" and method == "POST":
            b = self.body() or {}
            pid = b.get("patient_id")
            items = b.get("items") or []
            warnings = []
            allergies = rows(conn, "SELECT substance FROM patient_allergy WHERE patient_id=?", (pid,)) if pid else []
            names = " ".join((i.get("brand") or "") + " " + (i.get("generic") or "") for i in items).lower()
            for a in allergies:
                if a.get("substance") and a["substance"].lower() in names:
                    warnings.append("Allergy match: " + a["substance"])
            if "ibuprofen" in names and "diclofenac" in names:
                warnings.append("Duplicate NSAID therapy")
            if "amoxicillin" in names and "augmentin" in names:
                warnings.append("Duplicate penicillin")
            return {"warnings": warnings, "note": "AI suggestion – doctor to verify"}
        if path == "/api/rx/dispense" and method == "POST":
            b = self.body() or {}
            rid = b.get("rx_id")
            _exec(conn, "UPDATE rx_header SET status='dispensed' WHERE id=?", (rid,))
            _exec(conn, "INSERT INTO rx_audit(rx_id, action, user_name, at) VALUES (?,?,?,?)", (rid, "dispensed", user.get("full_name"), today()))
            return {"ok": True, "status": "dispensed"}
        if path == "/api/rx/reports":
            top = rows(conn, "SELECT d.brand, COUNT(*) n FROM rx_item i LEFT JOIN drug_master d ON d.id=i.drug_id GROUP BY d.brand ORDER BY n DESC LIMIT 10")
            by_doc = rows(conn, "SELECT doctor_id, COUNT(*) n FROM rx_header GROUP BY doctor_id")
            return {"top_drugs": top, "by_doctor": by_doc}

        if path == "/api/rx/drugs":
            q = (self.query.get("q") or [""])[0].strip().lower()
            drugs = rows(conn, "SELECT * FROM drug_master ORDER BY brand")
            if q:
                drugs = [d for d in drugs if q in (d.get("brand") or "").lower() or q in (d.get("generic") or "").lower()]
            return {"drugs": drugs[:30]}
        if path == "/api/rx/templates":
            tpls = rows(conn, "SELECT * FROM rx_template ORDER BY name")
            for t in tpls:
                t["items"] = rows(conn, "SELECT * FROM rx_template_item WHERE template_id=?", (t["id"],))
            return {"templates": tpls}
        if path == "/api/rx" and method == "POST":
            b = self.body() or {}
            import uuid
            token = uuid.uuid4().hex[:10]
            t = today()
            _exec(conn, "INSERT INTO rx_header(patient_id, doctor_id, date, diagnosis, notes, status, follow_up, token) VALUES (?,?,?,?,?,?,?,?)",
                  (b.get("patient_id"), b.get("doctor_id"), t, b.get("diagnosis"), b.get("notes"), "signed", b.get("follow_up"), token))
            hdr = rows(conn, "SELECT id FROM rx_header ORDER BY id DESC LIMIT 1")
            rid = hdr[0]["id"] if hdr else None
            for it in b.get("items") or []:
                _exec(conn, "INSERT INTO rx_item(rx_id, drug_id, dose, frequency, duration, quantity, route, timing, instructions) VALUES (?,?,?,?,?,?,?,?,?)",
                      (rid, it.get("drug_id"), it.get("dose"), it.get("frequency"), it.get("duration"), it.get("quantity") or 1, it.get("route"), it.get("timing"), it.get("instructions")))
            _exec(conn, "INSERT INTO rx_audit(rx_id, action, user_name, at) VALUES (?,?,?,?)", (rid, "signed", user.get("full_name"), t))
            return {"id": rid, "token": token, "verify": "/rx/verify/" + token}
        if path.startswith("/api/rx/verify/"):
            token = path.rsplit("/", 1)[-1]
            hdr = rows(conn, "SELECT h.*, p.name patient FROM rx_header h LEFT JOIN patients p ON p.id=h.patient_id WHERE h.token=?", (token,))
            if not hdr:
                return {"error": "not found"}
            items = rows(conn, "SELECT i.*, d.brand, d.generic, d.strength FROM rx_item i LEFT JOIN drug_master d ON d.id=i.drug_id WHERE i.rx_id=?", (hdr[0]["id"],))
            return {"rx": hdr[0], "items": items}
        if path == "/api/rx/queue":
            q = rows(conn, "SELECT h.*, p.name patient FROM rx_header h LEFT JOIN patients p ON p.id=h.patient_id WHERE h.status IN ('signed','partially_dispensed') ORDER BY h.id DESC")
            return {"queue": q}

        if path == "/api/rx/search":
            q = (self.query.get("q") or [""])[0].strip()
            like = "%" + q + "%"
            meds = rows(conn, "SELECT id, name, stock, unit_price FROM medicines WHERE name ILIKE ? OR ? = '' ORDER BY name LIMIT 20", (like, q)) if False else rows(conn, "SELECT id, name, stock, unit_price FROM medicines WHERE LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT 20", (like,))
            return {"medicines": meds}
        if path == "/api/rx/suggest" and method == "POST":
            b = self.body() or {}
            diagnosis = (b.get("diagnosis") or "").lower()
            meds = rows(conn, "SELECT id, name, stock, unit_price FROM medicines ORDER BY name")
            words = [w for w in diagnosis.replace(",", " ").split() if len(w) > 2]
            scored = []
            for m in meds:
                name = (m.get("name") or "").lower()
                score = sum(1 for w in words if w in name)
                if score:
                    scored.append((score, m))
            scored.sort(key=lambda x: -x[0])
            hits = [m for _, m in scored[:8]]
            if len(hits) < 4:
                for m in meds:
                    if m not in hits:
                        hits.append(m)
                    if len(hits) >= 6:
                        break
            return {"suggestions": hits, "note": "Multiple options — doctor must review", "source": "catalog-match"}

        if path == "/api/tokens" and method == "GET":
            t = today()
            return {"date": t, "tokens": rows(conn, "SELECT q.*, p.name patient, s.name doctor FROM queue_tokens q LEFT JOIN patients p ON p.id=q.patient_id LEFT JOIN staff s ON s.id=q.doctor_id WHERE q.date=? ORDER BY q.number", (t,))}
        if path == "/api/tokens" and method == "POST":
            b = self.body() or {}
            t = today()
            n = scalar(conn, "SELECT COALESCE(MAX(number),0)+1 FROM queue_tokens WHERE date=?", (t,)) or 1
            _exec(conn, "INSERT INTO queue_tokens(patient_id, doctor_id, date, number, status, created_at) VALUES (?,?,?,?,?,?)",
                  (b.get("patient_id"), b.get("doctor_id"), t, n, "waiting", t))
            if getattr(__import__("app.models.db", fromlist=["db"]), "USE_POSTGRES", False):
                conn.commit()
            return {"number": n, "date": t}
        if path == "/api/doctor-shares" and method == "GET":
            return {"rules": rows(conn, "SELECT r.*, s.name doctor FROM doctor_share_rules r LEFT JOIN staff s ON s.id=r.doctor_id")}
        if path == "/api/doctor-shares" and method == "POST":
            b = self.body() or {}
            _exec(conn, "INSERT INTO doctor_share_rules(doctor_id, service, share_type, value) VALUES (?,?,?,?)",
                  (b.get("doctor_id"), b.get("service") or "Consultation", b.get("share_type") or "percent", b.get("value") or 0))
            return {"ok": True}
        if path == "/api/panels" and method == "GET":
            return {"panels": rows(conn, "SELECT * FROM panels ORDER BY name")}
        if path == "/api/panels" and method == "POST":
            b = self.body() or {}
            _exec(conn, "INSERT INTO panels(name, panel_type, discount) VALUES (?,?,?)", (b.get("name"), b.get("panel_type") or "corporate", b.get("discount") or 0))
            return {"ok": True}
        if path == "/api/pharmacy/batches" and method == "GET":
            return {"batches": rows(conn, "SELECT b.*, m.name medicine FROM medicine_batches b LEFT JOIN medicines m ON m.id=b.medicine_id ORDER BY b.expiry")}
        if path == "/api/pharmacy/batches" and method == "POST":
            b = self.body() or {}
            _exec(conn, "INSERT INTO medicine_batches(medicine_id, batch_no, expiry, qty, cost) VALUES (?,?,?,?,?)",
                  (b.get("medicine_id"), b.get("batch_no"), b.get("expiry"), b.get("qty") or 0, b.get("cost") or 0))
            return {"ok": True}
        if path == "/api/fbr/submit" and method == "POST":
            b = self.body() or {}
            return {"mode": "sandbox", "fbr_invoice_no": "FBR-MOCK-%s" % (b.get("invoice_id") or "0"), "qr": "sandbox"}
        if path == "/api/notify" and method == "POST":
            b = self.body() or {}
            t = today()
            _exec(conn, "INSERT INTO message_log(channel, to_addr, body, status, created_at) VALUES (?,?,?,?,?)",
                  (b.get("channel") or "whatsapp", b.get("to") or "", b.get("body") or "", "mock-sent", t))
            return {"status": "mock-sent"}
        if path == "/api/portal/me":
            pid = user.get("patient_id")
            if not pid:
                return {"patient": None, "appointments": [], "invoices": []}
            appts = rows(conn, "SELECT date, time, reason, status FROM appointments WHERE patient_id=? ORDER BY date DESC LIMIT 10", (pid,))
            invs = rows(conn, "SELECT number, date, total, paid, status FROM invoices WHERE patient_id=? ORDER BY date DESC LIMIT 10", (pid,))
            return {"patient_id": pid, "appointments": appts, "invoices": invs}
        if path == "/api/backup" and method == "POST":
            return {"ok": True, "note": "Backup requested. On PostgreSQL run pg_dump. On SQLite copy database/hospital.db."}

        if path == "/api/branches":
            return {"branches": [{"id": 1, "name": "Main", "city": "Karachi"}]}

        if path == "/api/inventory/alerts":
            from app.models import db as db_mod
            exp_expr = "(CURRENT_DATE + INTERVAL '90 days')::date" if getattr(db_mod, "USE_POSTGRES", False) else "date('now','+90 day')"
            low = rows(conn, "SELECT id, name, stock, reorder_level, expiry_date, unit_price FROM medicines WHERE stock<=reorder_level ORDER BY stock")
            exp = rows(conn, f"SELECT id, name, stock, reorder_level, expiry_date, unit_price FROM medicines WHERE expiry_date::date<={exp_expr} ORDER BY expiry_date" if getattr(db_mod, "USE_POSTGRES", False) else "SELECT id, name, stock, reorder_level, expiry_date, unit_price FROM medicines WHERE expiry_date<=date('now','+90 day') ORDER BY expiry_date")
            return {"low_stock": low, "expiring": exp}

        m = re.fullmatch(r"/api/admissions/(\d+)/summary", path)
        if m and method == "GET":
            aid = int(m.group(1))
            adm = one(conn, """SELECT a.*, p.name patient, p.mrn, p.gender, p.dob, p.allergies, d.name doctor, w.name ward, b.bed_no
                FROM admissions a JOIN patients p ON p.id=a.patient_id JOIN staff d ON d.id=a.doctor_id
                JOIN beds b ON b.id=a.bed_id JOIN wards w ON w.id=b.ward_id WHERE a.id=?""", (aid,))
            if not adm:
                raise ApiError(404, "Admission not found")
            labs = rows(conn, "SELECT t.name test, o.result, o.status FROM lab_orders o JOIN lab_tests t ON t.id=o.test_id WHERE o.patient_id=? ORDER BY o.id DESC LIMIT 10", (adm["patient_id"],))
            rxs = rows(conn, "SELECT medicine, dosage, frequency, duration, instructions FROM prescriptions WHERE patient_id=? ORDER BY id DESC LIMIT 10", (adm["patient_id"],))
            s = get_settings(conn)
            html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Discharge Summary</title>
            <style>body{{font-family:sans-serif;margin:40px}} h1{{margin:0}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:6px;text-align:left}}</style></head>
            <body><h1>{s.get('hospital_name','Hospital')}</h1><p>{s.get('address','')}</p>
            <h2>Discharge Summary</h2>
            <p><b>Patient:</b> {adm['patient']} ({adm['mrn']}) &nbsp; <b>Gender:</b> {adm.get('gender') or '—'} &nbsp; <b>DOB:</b> {adm.get('dob') or '—'}</p>
            <p><b>Allergies:</b> {adm.get('allergies') or 'None'}</p>
            <p><b>Admitted:</b> {adm['admit_date']} &nbsp; <b>Discharged:</b> {adm.get('discharge_date') or '—'} &nbsp; <b>Ward:</b> {adm['ward']} Bed {adm['bed_no']}</p>
            <p><b>Doctor:</b> {adm['doctor']}</p>
            <h3>Diagnosis</h3><p>{adm.get('diagnosis') or '—'}</p>
            <h3>Recent Labs</h3><table><tr><th>Test</th><th>Result</th><th>Status</th></tr>
            {''.join(f"<tr><td>{l['test']}</td><td>{l.get('result') or '—'}</td><td>{l['status']}</td></tr>" for l in labs) or '<tr><td colspan=3>None</td></tr>'}
            </table>
            <h3>Prescriptions</h3><table><tr><th>Medicine</th><th>Dosage</th><th>Frequency</th><th>Duration</th></tr>
            {''.join(f"<tr><td>{r['medicine']}</td><td>{r.get('dosage') or ''}</td><td>{r.get('frequency') or ''}</td><td>{r.get('duration') or ''}</td></tr>" for r in rxs) or '<tr><td colspan=4>None</td></tr>'}
            </table>
            <p style='margin-top:40px'>_________________________<br>Doctor signature</p>
            <script>window.print()</script></body></html>"""
            return (html.encode(), {"Content-Type": "text/html; charset=utf-8"})
        if path == "/api/accounts/gl":
            if role not in ("Admin", "Accountant"):
                raise ApiError(403, "Not permitted")
            return gl_summary(conn)

        m = re.fullmatch(r"/api/patients/(\d+)/profile", path)
        if m:
            pid = int(m.group(1))
            get_res("patients", user, "read")
            if role == "Patient" and user.get("patient_id") and pid != user["patient_id"]:
                raise ApiError(403, "Cannot view another patient's profile")
            if role not in ("Admin", "Doctor", "Nurse", "Patient"):
                p = patient_profile(conn, pid)
                for k in ("encounters", "labs", "medicines"):
                    p[k] = []
                return p
            return patient_profile(conn, pid)

        m = re.fullmatch(r"/api/admissions/(\d+)/discharge", path)
        if m and method == "POST":
            get_res("admissions", user, "write")
            return discharge(conn, int(m.group(1)), user)

        # 8. Invoice & Payment Controller routes
        m = re.fullmatch(r"/api/invoices/(\d+)(?:/(items|payments))?", path)
        if m:
            get_res("invoices", user, "read" if method == "GET" else "write")
            iid, sub = int(m.group(1)), m.group(2)
            if method == "GET" and not sub:
                return invoice_detail(conn, iid)
            if method == "POST" and sub == "items":
                b = self.body()
                try:
                    amt = float(b.get("amount"))
                except (TypeError, ValueError):
                    raise ApiError(400, "Valid amount required")
                if not b.get("description"):
                    raise ApiError(400, "Description required")
                conn.execute("INSERT INTO invoice_items(invoice_id,description,amount) VALUES(?,?,?)", (iid, b["description"], amt))
                recompute(conn, iid)
                audit(conn, user, "invoice item", f"invoice #{iid}")
                return invoice_detail(conn, iid)
            if method == "POST" and sub == "payments":
                b = self.body()
                try:
                    amt = float(b.get("amount"))
                except (TypeError, ValueError):
                    raise ApiError(400, "Valid amount required")
                inv = one(conn, "SELECT total, paid FROM invoices WHERE id=?", (iid,))
                if amt <= 0:
                    raise ApiError(400, "Amount must be positive")
                if amt > inv["total"] - inv["paid"] + 0.001:
                    raise ApiError(400, f"Payment exceeds balance ({inv['total'] - inv['paid']:.2f})")
                conn.execute("INSERT INTO payments(invoice_id,amount,method,date) VALUES(?,?,?,?)", (iid, amt, b.get("method") or "Cash", today()))
                recompute(conn, iid)
                audit(conn, user, "payment", f"invoice #{iid} amount {amt}")
                return invoice_detail(conn, iid)
            if method == "DELETE" and sub == "items":
                raise ApiError(400, "Use item id endpoint")

        m = re.fullmatch(r"/api/invoice_items/(\d+)", path)
        if m and method == "DELETE":
            get_res("invoices", user, "write")
            it = one(conn, "SELECT invoice_id FROM invoice_items WHERE id=?", (int(m.group(1)),))
            if it:
                conn.execute("DELETE FROM invoice_items WHERE id=?", (int(m.group(1)),))
                recompute(conn, it["invoice_id"])
            return {"ok": True}

        # 9. Generic Resource CRUD Controller routes
        m = re.fullmatch(r"/api/r/(\w+)(?:/(\d+))?", path)
        if m:
            key, id_ = m.group(1), m.group(2)
            if method == "GET":
                r = get_res(key, user, "read")
                data = rows(conn, r["sql"])
                if role == "Patient" and user.get("patient_id"):
                    pid = user["patient_id"]
                    if key == "patients":
                        data = [x for x in data if x.get("id") == pid]
                    elif data and "patient_id" in data[0]:
                        data = [x for x in data if x.get("patient_id") == pid]
                q = (qs.get("q", [""])[0]).lower()
                if q:
                    data = [x for x in data if q in " ".join(str(v) for v in x.values()).lower()]
                return data
            if method == "POST" and not id_:
                body = self.body()
                if role == "Patient" and user.get("patient_id"):
                    body["patient_id"] = user["patient_id"]
                return {"id": create(conn, key, body, user)}
            if method == "PUT" and id_:
                update(conn, key, int(id_), self.body(), user)
                return {"ok": True}
            if method == "DELETE" and id_:
                delete(conn, key, int(id_), user)
                return {"ok": True}

        m = re.fullmatch(r"/api/record/(\w+)/(\d+)", path)
        if m and method == "GET":
            r = get_res(m.group(1), user, "read")
            rec = one(conn, f"SELECT * FROM {r['table']} WHERE id=?", (int(m.group(2)),))
            if not rec:
                raise ApiError(404, "Not found")
            rec.pop("password_hash", None)
            return rec
        raise ApiError(404, "Unknown endpoint")


class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _get_lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_server(port):
    import subprocess
    import signal
    import time
    host = os.environ.get("HOST", "0.0.0.0")
    try:
        httpd = ReusableHTTPServer((host, port), Handler)
    except OSError:
        try:
            out = subprocess.check_output(["/usr/sbin/lsof", "-ti", f"tcp:{port}"], text=True)
            for p in out.split():
                pid = int(p)
                if pid != os.getpid():
                    os.kill(pid, signal.SIGTERM)
            time.sleep(0.4)
        except Exception:
            pass
        httpd = ReusableHTTPServer((host, port), Handler)
    lan_ip = _get_lan_ip()
    print(f"{HOSPITAL_NAME} HMS (MVC) running on:")
    print(f"  • This computer:   http://localhost:{port}")
    print(f"  • Same Wi-Fi/LAN:  http://{lan_ip}:{port}")
    print(f"  • Database file:   {DB}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(DB):
        os.remove(DB)
    init_db()
    port = int(os.environ.get("PORT", 8000))
    start_server(port)
