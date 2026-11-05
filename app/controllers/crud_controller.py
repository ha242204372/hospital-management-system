"""CRUD & clinical workflow controller: validation, hooks, admission/discharge, and auto-billing."""
import sqlite3
import datetime as dt
from app.config import ApiError
from app.models.db import one, scalar, today, audit, add_charge, get_settings, _exec, USE_POSTGRES
from app.models.schema_registry import RES
from app.controllers.auth_controller import hash_pw


def get_res(key, user, mode):
    r = RES.get(key)
    if not r:
        raise ApiError(404, "Unknown resource")
    if user["role"] not in r[mode]:
        raise ApiError(403, "Not permitted for your role")
    return r


def clean(r, data, creating):
    out = {}
    for f in r["fields"]:
        n = f["name"]
        if n in data:
            v = data[n]
            if f["type"] in ("number", "ref") and v not in ("", None):
                try:
                    v = float(v) if f["type"] == "number" else int(v)
                    if v == int(v):
                        v = int(v)
                except ValueError:
                    raise ApiError(400, f"Invalid value for {f['label']}")
            if v == "":
                v = None
            out[n] = v
        elif creating and "default" in f:
            out[n] = f["default"]
    if creating:
        for f in r["fields"]:
            if f.get("required") and out.get(f["name"]) in (None, ""):
                raise ApiError(400, f"{f['label']} is required")
    return out


def hook_before_create(conn, res, d, user):
    if res == "patients":
        pfx = (get_settings(conn).get("mrn_prefix") or "MRN").strip()
        d["mrn"] = "%s%05d" % (pfx, scalar(conn, "SELECT MAX(id) FROM patients") + 1)
    elif res == "admissions":
        b = one(conn, "SELECT status FROM beds WHERE id=?", (d["bed_id"],))
        if not b or b["status"] != "Available":
            raise ApiError(400, "Selected bed is not available")
        d["status"] = "Admitted"
    elif res == "lab_orders":
        d["ordered_at"] = d.get("ordered_at") or today()
    elif res == "dispensing":
        m = one(conn, "SELECT * FROM medicines WHERE id=?", (d["medicine_id"],))
        q = int(d["quantity"])
        if q <= 0:
            raise ApiError(400, "Quantity must be positive")
        if not m or m["stock"] < q:
            raise ApiError(400, f"Insufficient stock (available: {m['stock'] if m else 0})")
        d["amount"] = round(q * m["unit_price"], 2)
        d["date"] = d.get("date") or today()
    elif res == "invoices":
        n = scalar(conn, "SELECT MAX(id) FROM invoices") + 1
        pfx = (get_settings(conn).get("invoice_prefix") or "INV").strip().rstrip("-")
        d["number"] = f"{pfx}-{n:05d}"
        d["date"] = d.get("date") or today()
    elif res == "users":
        pw = d.pop("password", "")
        if not pw:
            raise ApiError(400, "Password required")
        d["password_hash"] = hash_pw(pw)


def hook_after_create(conn, res, id_, d):
    if res == "admissions":
        _exec(conn, "UPDATE beds SET status='Occupied' WHERE id=?", (d["bed_id"],))
    elif res == "encounters":
        doc = one(conn, "SELECT name, fee FROM staff WHERE id=?", (d["doctor_id"],))
        if doc and doc["fee"]:
            add_charge(conn, d["patient_id"], f"Consultation – {doc['name']} ({d['date']})", doc["fee"])
        _exec(conn, 
            "UPDATE appointments SET status='Completed' WHERE patient_id=? AND doctor_id=? AND date=? AND status='Scheduled'",
            (d["patient_id"], d["doctor_id"], d["date"]),
        )
    elif res == "lab_orders":
        t = one(conn, "SELECT name, price FROM lab_tests WHERE id=?", (d["test_id"],))
        add_charge(conn, d["patient_id"], f"Lab – {t['name']}", t["price"])
    elif res == "dispensing":
        _exec(conn, "UPDATE medicines SET stock=stock-? WHERE id=?", (int(d["quantity"]), d["medicine_id"]))
        m = one(conn, "SELECT name FROM medicines WHERE id=?", (d["medicine_id"],))
        add_charge(conn, d["patient_id"], f"Pharmacy – {m['name']} x{d['quantity']}", d["amount"])


def hook_before_update(conn, res, id_, d):
    if res == "users":
        pw = d.pop("password", "")
        if pw:
            d["password_hash"] = hash_pw(pw)
    elif res == "admissions":
        old = one(conn, "SELECT * FROM admissions WHERE id=?", (id_,))
        if old["status"] == "Discharged":
            raise ApiError(400, "Discharged admissions cannot be edited")
        if "bed_id" in d and int(d["bed_id"]) != old["bed_id"]:
            b = one(conn, "SELECT status FROM beds WHERE id=?", (d["bed_id"],))
            if not b or b["status"] != "Available":
                raise ApiError(400, "Selected bed is not available")
            _exec(conn, "UPDATE beds SET status='Available' WHERE id=?", (old["bed_id"],))
            _exec(conn, "UPDATE beds SET status='Occupied' WHERE id=?", (d["bed_id"],))
    elif res == "invoices":
        d.pop("patient_id", None)


def hook_before_delete(conn, res, id_):
    if res == "admissions":
        a = one(conn, "SELECT * FROM admissions WHERE id=?", (id_,))
        if a and a["status"] == "Admitted":
            _exec(conn, "UPDATE beds SET status='Available' WHERE id=?", (a["bed_id"],))


def create(conn, key, data, user):
    r = get_res(key, user, "write")
    data = dict(data)
    if key == "admissions" and not data.get("admit_date"):
        data["admit_date"] = today()
    if key in ("encounters", "appointments", "dispensing", "invoices") and not data.get("date"):
        data["date"] = today()
    if key == "lab_orders" and not data.get("ordered_at"):
        data["ordered_at"] = today()
    d = clean(r, data, True)
    hook_before_create(conn, key, d, user)
    cols = list(d.keys())
    if USE_POSTGRES:
        _exec(conn, 
            f"INSERT INTO {r['table']}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            [d[c] for c in cols],
        )
        new_id = scalar(conn, f"SELECT MAX(id) FROM {r['table']}")
    else:
        cur = _exec(conn, 
            f"INSERT INTO {r['table']}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            [d[c] for c in cols],
        )
        new_id = cur.lastrowid
    hook_after_create(conn, key, new_id, d)
    audit(conn, user, "create", f"{key} #{new_id}")
    return new_id


def update(conn, key, id_, data, user):
    r = get_res(key, user, "write")
    if r.get("no_edit"):
        raise ApiError(400, "This record cannot be edited")
    d = clean(r, data, False)
    hook_before_update(conn, key, id_, d)
    if not d:
        return
    _exec(conn, 
        f"UPDATE {r['table']} SET {','.join(c + '=?' for c in d)} WHERE id=?",
        list(d.values()) + [id_],
    )
    audit(conn, user, "update", f"{key} #{id_}")


def delete(conn, key, id_, user):
    r = get_res(key, user, "delete")
    hook_before_delete(conn, key, id_)
    try:
        _exec(conn, f"DELETE FROM {r['table']} WHERE id=?", (id_,))
    except sqlite3.IntegrityError:
        raise ApiError(409, "Cannot delete: record is referenced by other data")
    audit(conn, user, "delete", f"{key} #{id_}")


def discharge(conn, id_, user):
    a = one(
        conn,
        "SELECT a.*, b.bed_no, w.name ward, w.daily_rate FROM admissions a JOIN beds b ON b.id=a.bed_id JOIN wards w ON w.id=b.ward_id WHERE a.id=?",
        (id_,),
    )
    if not a or a["status"] != "Admitted":
        raise ApiError(400, "Not an active admission")
    days = max(1, (dt.date.today() - dt.date.fromisoformat(a["admit_date"])).days)
    amount = days * (a["daily_rate"] or 0)
    inv = None
    if amount:
        inv = add_charge(
            conn,
            a["patient_id"],
            f"Bed charges – {a['ward']} bed {a['bed_no']} ({days} day{'s' if days > 1 else ''})",
            amount,
        )
    _exec(conn, "UPDATE admissions SET status='Discharged', discharge_date=? WHERE id=?", (today(), id_))
    _exec(conn, "UPDATE beds SET status='Available' WHERE id=?", (a["bed_id"],))
    audit(conn, user, "discharge", f"admission #{id_}")
    return {"days": days, "amount": amount, "invoice_id": inv}
