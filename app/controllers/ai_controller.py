"""Gemini AI Hub controller: Symptom Triage, SOAP Copilot, Longitudinal EMR Summary, Rx Safety, and Executive Briefing."""
import gemini_ai
from app.config import ApiError
from app.models.db import one, rows, audit
from app.controllers.analytics_controller import patient_profile, dashboard


def handle_ai_route(conn, method, path, user, body_fn):
    role = user["role"]
    if path == "/api/ai/status" and method == "GET":
        return gemini_ai.get_status()

    if path == "/api/ai/config" and method == "POST":
        if role not in ("Admin", "Doctor"):
            raise ApiError(403, "Only Admin or Doctor can update Gemini settings")
        b = body_fn()
        gemini_ai.set_runtime_config(api_key=b.get("api_key"), model=b.get("model"))
        audit(conn, user, "ai_config", f"model={b.get('model')}")
        return gemini_ai.get_status()

    if path == "/api/ai/triage" and method == "POST":
        b = body_fn()
        if not (b.get("symptoms") or "").strip():
            raise ApiError(400, "Please describe presenting symptoms")
        try:
            out = gemini_ai.ai_triage(
                symptoms=b["symptoms"],
                age=b.get("age"),
                gender=b.get("gender"),
                vitals=b.get("vitals"),
                model=b.get("model"),
            )
            audit(conn, user, "ai_triage", b["symptoms"][:80])
            return out
        except RuntimeError as e:
            raise ApiError(502, str(e))

    if path == "/api/ai/copilot" and method == "POST":
        if role not in ("Admin", "Doctor", "Nurse"):
            raise ApiError(403, "Not permitted")
        b = body_fn()
        pat = one(conn, "SELECT * FROM patients WHERE id=?", (int(b["patient_id"]),)) if b.get("patient_id") else None
        try:
            out = gemini_ai.ai_clinical_copilot(
                brief_notes=b.get("notes", ""),
                patient=pat,
                vitals={"bp": b.get("bp"), "temperature": b.get("temperature"), "pulse": b.get("pulse"), "weight": b.get("weight")},
                model=b.get("model"),
            )
            audit(conn, user, "ai_copilot", f"patient #{b.get('patient_id')}")
            return out
        except RuntimeError as e:
            raise ApiError(502, str(e))

    if path == "/api/ai/patient-summary" and method == "POST":
        b = body_fn()
        pid = int(b.get("patient_id") or 0)
        if not pid:
            raise ApiError(400, "patient_id required")
        if role == "Patient" and user.get("patient_id") and pid != user["patient_id"]:
            raise ApiError(403, "Cannot view another patient's summary")
        prof = patient_profile(conn, pid)
        try:
            out = gemini_ai.ai_patient_summary(prof, model=b.get("model"))
            audit(conn, user, "ai_patient_summary", f"patient #{pid}")
            return out
        except RuntimeError as e:
            raise ApiError(502, str(e))

    if path == "/api/ai/rx-check" and method == "POST":
        b = body_fn()
        pat = one(conn, "SELECT * FROM patients WHERE id=?", (int(b["patient_id"]),)) if b.get("patient_id") else None
        existing = (
            [m["medicine"] for m in rows(conn, "SELECT m.name medicine FROM dispensing s JOIN medicines m ON m.id=s.medicine_id WHERE s.patient_id=? ORDER BY s.id DESC LIMIT 10", (pat["id"],))]
            if pat else []
        )
        try:
            out = gemini_ai.ai_Rx_safety_check(
                medicines_list=b.get("medicines") or [],
                allergies=(pat or {}).get("allergies") or b.get("allergies") or "",
                existing_meds=existing,
                model=b.get("model"),
            )
            audit(conn, user, "ai_rx_check", f"patient #{b.get('patient_id')}")
            return out
        except RuntimeError as e:
            raise ApiError(502, str(e))

    if path == "/api/ai/briefing" and method == "POST":
        b = body_fn()
        dash = dashboard(conn)
        try:
            out = gemini_ai.ai_executive_briefing(
                kpis=dash["kpis"],
                extra_context={"wards": dash["wards"], "low_stock_list": dash["low_stock_list"], "by_department": dash["by_department"]},
                question=b.get("question"),
                previous_interaction_id=b.get("previous_interaction_id"),
                model=b.get("model"),
            )
            audit(conn, user, "ai_briefing", (b.get("question") or "daily_briefing")[:80])
            return out
        except RuntimeError as e:
            raise ApiError(502, str(e))

    return None
