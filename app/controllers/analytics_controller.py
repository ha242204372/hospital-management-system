"""Analytics & profile controller: Dashboard KPIs, 30-day Reports, Patient Profile, and Invoice Detail."""
import datetime as dt
from app.config import ApiError, HOSPITAL_NAME
from app.models.db import rows, one, scalar, today, get_settings


def invoice_detail(conn, id_):
    inv = one(
        conn,
        "SELECT i.*, p.name patient, p.mrn, p.phone, p.address FROM invoices i JOIN patients p ON p.id=i.patient_id WHERE i.id=?",
        (id_,),
    )
    if not inv:
        raise ApiError(404, "Invoice not found")
    s = get_settings(conn)
    inv["items"] = rows(conn, "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (id_,))
    inv["payments"] = rows(conn, "SELECT * FROM payments WHERE invoice_id=? ORDER BY id", (id_,))
    inv["hospital"] = s.get("hospital_name") or HOSPITAL_NAME
    inv["hospital_info"] = s
    return inv


def patient_profile(conn, id_):
    p = one(conn, "SELECT * FROM patients WHERE id=?", (id_,))
    if not p:
        raise ApiError(404, "Patient not found")
    p["appointments"] = rows(
        conn,
        "SELECT a.date, a.time, a.reason, a.status, d.name doctor FROM appointments a JOIN staff d ON d.id=a.doctor_id WHERE patient_id=? ORDER BY a.date DESC LIMIT 20",
        (id_,),
    )
    p["encounters"] = rows(
        conn,
        "SELECT e.*, d.name doctor FROM encounters e JOIN staff d ON d.id=e.doctor_id WHERE patient_id=? ORDER BY e.date DESC LIMIT 20",
        (id_,),
    )
    p["admissions"] = rows(
        conn,
        "SELECT a.admit_date, a.discharge_date, a.status, a.diagnosis, w.name ward, b.bed_no FROM admissions a JOIN beds b ON b.id=a.bed_id JOIN wards w ON w.id=b.ward_id WHERE patient_id=? ORDER BY a.admit_date DESC",
        (id_,),
    )
    p["labs"] = rows(
        conn,
        "SELECT o.ordered_at, t.name test, o.status, o.result, t.reference_range FROM lab_orders o JOIN lab_tests t ON t.id=o.test_id WHERE patient_id=? ORDER BY o.id DESC",
        (id_,),
    )
    p["medicines"] = rows(
        conn,
        "SELECT s.date, m.name medicine, s.quantity FROM dispensing s JOIN medicines m ON m.id=s.medicine_id WHERE patient_id=? ORDER BY s.id DESC",
        (id_,),
    )
    p["invoices"] = rows(
        conn,
        "SELECT id, number, date, total, paid, status FROM invoices WHERE patient_id=? ORDER BY id DESC",
        (id_,),
    )
    return p


def days_back(n):
    return [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def dashboard(conn):
    t = today()
    month = t[:7]
    k = {
        "patients": scalar(conn, "SELECT COUNT(*) FROM patients"),
        "new_patients_month": scalar(conn, "SELECT COUNT(*) FROM patients WHERE created_at LIKE ?", (month + "%",)),
        "appointments_today": scalar(conn, "SELECT COUNT(*) FROM appointments WHERE date=?", (t,)),
        "admitted": scalar(conn, "SELECT COUNT(*) FROM admissions WHERE status='Admitted'"),
        "beds_total": scalar(conn, "SELECT COUNT(*) FROM beds"),
        "beds_occupied": scalar(conn, "SELECT COUNT(*) FROM beds WHERE status='Occupied'"),
        "revenue_today": scalar(conn, "SELECT SUM(amount) FROM payments WHERE date=?", (t,)),
        "revenue_month": scalar(conn, "SELECT SUM(amount) FROM payments WHERE date LIKE ?", (month + "%",)),
        "outstanding": scalar(conn, "SELECT SUM(total-paid) FROM invoices"),
        "low_stock": scalar(conn, "SELECT COUNT(*) FROM medicines WHERE stock<=reorder_level"),
        "expiring": scalar(conn, "SELECT COUNT(*) FROM medicines WHERE expiry_date<=date('now','+90 day')"),
        "pending_labs": scalar(conn, "SELECT COUNT(*) FROM lab_orders WHERE status!='Completed'"),
        "doctors": scalar(conn, "SELECT COUNT(*) FROM staff WHERE role='Doctor' AND status='Active'"),
    }
    d7 = days_back(7)
    ap = {r["date"]: r["c"] for r in rows(conn, "SELECT date, COUNT(*) c FROM appointments WHERE date>=? GROUP BY date", (d7[0],))}
    d14 = days_back(14)
    rv = {r["date"]: r["s"] for r in rows(conn, "SELECT date, SUM(amount) s FROM payments WHERE date>=? GROUP BY date", (d14[0],))}
    return {
        "kpis": k,
        "appointments_7d": [{"label": d[5:], "value": ap.get(d, 0)} for d in d7],
        "revenue_14d": [{"label": d[5:], "value": rv.get(d, 0)} for d in d14],
        "wards": rows(conn, "SELECT w.name, COUNT(b.id) total, SUM(b.status='Occupied') occupied FROM wards w LEFT JOIN beds b ON b.ward_id=w.id GROUP BY w.id"),
        "appointment_status": rows(conn, "SELECT status label, COUNT(*) value FROM appointments GROUP BY status"),
        "by_department": rows(conn, "SELECT COALESCE(dp.name,'—') label, COUNT(*) value FROM appointments a JOIN staff s ON s.id=a.doctor_id LEFT JOIN departments dp ON dp.id=s.department_id GROUP BY dp.id ORDER BY value DESC"),
        "invoice_status": rows(conn, "SELECT status label, COUNT(*) value FROM invoices GROUP BY status"),
        "upcoming": rows(conn, "SELECT a.date, a.time, p.name patient, d.name doctor, a.status FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN staff d ON d.id=a.doctor_id WHERE a.date>=? AND a.status='Scheduled' ORDER BY a.date, a.time LIMIT 8", (t,)),
        "recent_admissions": rows(conn, "SELECT a.admit_date, p.name patient, w.name ward, b.bed_no, a.status FROM admissions a JOIN patients p ON p.id=a.patient_id JOIN beds b ON b.id=a.bed_id JOIN wards w ON w.id=b.ward_id ORDER BY a.id DESC LIMIT 6"),
        "low_stock_list": rows(conn, "SELECT name, stock, reorder_level, expiry_date FROM medicines WHERE stock<=reorder_level OR expiry_date<=date('now','+90 day') ORDER BY stock LIMIT 6"),
    }


def reports(conn):
    d30 = days_back(30)
    rv = {r["date"]: r["s"] for r in rows(conn, "SELECT date, SUM(amount) s FROM payments WHERE date>=? GROUP BY date", (d30[0],))}
    return {
        "revenue_30d": [{"label": d[5:], "value": rv.get(d, 0)} for d in d30],
        "payment_methods": rows(conn, "SELECT COALESCE(method,'—') label, SUM(amount) value FROM payments GROUP BY method"),
        "top_diagnoses": rows(conn, "SELECT diagnosis label, COUNT(*) value FROM encounters WHERE diagnosis IS NOT NULL GROUP BY diagnosis ORDER BY value DESC LIMIT 8"),
        "top_medicines": rows(conn, "SELECT m.name label, SUM(s.quantity) value FROM dispensing s JOIN medicines m ON m.id=s.medicine_id GROUP BY m.id ORDER BY value DESC LIMIT 8"),
        "lab_usage": rows(conn, "SELECT t.name label, COUNT(*) value FROM lab_orders o JOIN lab_tests t ON t.id=o.test_id GROUP BY t.id ORDER BY value DESC LIMIT 8"),
        "doctor_workload": rows(
            conn,
            "SELECT s.name doctor, COALESCE(dp.name,'—') department, (SELECT COUNT(*) FROM appointments WHERE doctor_id=s.id) appointments, "
            "(SELECT COUNT(*) FROM encounters WHERE doctor_id=s.id) consultations, (SELECT COUNT(*) FROM admissions WHERE doctor_id=s.id) admissions "
            "FROM staff s LEFT JOIN departments dp ON dp.id=s.department_id WHERE s.role='Doctor' ORDER BY appointments DESC",
        ),
        "gender": rows(conn, "SELECT COALESCE(gender,'Unknown') label, COUNT(*) value FROM patients GROUP BY gender"),
        "age_groups": rows(
            conn,
            "SELECT CASE WHEN a<13 THEN '0-12' WHEN a<19 THEN '13-18' WHEN a<36 THEN '19-35' WHEN a<56 THEN '36-55' ELSE '56+' END label, COUNT(*) value FROM "
            "(SELECT CAST((julianday('now')-julianday(dob))/365.25 AS INT) a FROM patients WHERE dob IS NOT NULL AND dob!='') GROUP BY label",
        ),
    }
