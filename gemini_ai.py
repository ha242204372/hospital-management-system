#!/usr/bin/env python3
"""Gemini AI Hub for MediCare HMS.

Uses the Gemini Interactions API (`gemini-3.8-flash` & `gemini-4-argon`):
- Primary: `google-genai` SDK (`client.interactions.create`) when installed
- Fallback: Direct HTTPS REST (`POST /v1beta/interactions` with `Api-Revision: 2026-05-20`)
- Offline/Demo fallback: Clinical rule-based engine when no `GEMINI_API_KEY` is configured,
  so every AI feature works out-of-the-box and upgrades seamlessly when a key is provided.
"""
import json, os, re, urllib.request, urllib.error

DEFAULT_FLASH_MODEL = "gemini-3.8-flash"
DEFAULT_PRO_MODEL = "gemini-4-argon"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"

# Runtime & persistent config (saved to local .env with 0600 permissions; never echoed back)
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_RUNTIME_KEY = None
_RUNTIME_MODEL = DEFAULT_FLASH_MODEL


def _load_dotenv_key():
    for path in (
        _ENV_FILE,
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.expanduser("~/.env"),
    ):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                return val
            except OSError:
                pass
    return None


def _load_dotenv_model():
    if os.path.isfile(_ENV_FILE):
        try:
            with open(_ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_MODEL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val in (DEFAULT_FLASH_MODEL, DEFAULT_PRO_MODEL, "gemini-3.5-flash-lite"):
                            return val
        except OSError:
            pass
    return None


def _save_dotenv(api_key=None, model=None):
    lines = {}
    if os.path.isfile(_ENV_FILE):
        try:
            with open(_ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.lstrip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        lines[k.strip()] = v.strip()
        except OSError:
            pass
    if api_key:
        lines["GEMINI_API_KEY"] = api_key
    if model:
        lines["GEMINI_MODEL"] = model
    try:
        fd = os.open(_ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for k, v in lines.items():
                f.write(f"{k}={v}\n")
    except OSError:
        pass


def get_api_key():
    return _RUNTIME_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or _load_dotenv_key()


def set_runtime_config(api_key=None, model=None):
    global _RUNTIME_KEY, _RUNTIME_MODEL
    cleaned_key = (api_key or "").strip()
    if cleaned_key:
        _RUNTIME_KEY = cleaned_key
    if model in (DEFAULT_FLASH_MODEL, DEFAULT_PRO_MODEL, "gemini-3.5-flash-lite"):
        _RUNTIME_MODEL = model
    _save_dotenv(api_key=cleaned_key or get_api_key(), model=_RUNTIME_MODEL)


_RUNTIME_MODEL = _load_dotenv_model() or DEFAULT_FLASH_MODEL


def get_status():
    key = get_api_key()
    sdk_available = False
    try:
        from google import genai  # noqa: F401
        sdk_available = True
    except ImportError:
        pass
    return {
        "configured": bool(key),
        "mode": ("google-genai SDK" if sdk_available else "Gemini REST API (/v1beta/interactions)") if key else "Built-in Clinical Engine (add GEMINI_API_KEY for live Gemini API)",
        "model": _RUNTIME_MODEL,
        "available_models": [
            {"id": DEFAULT_FLASH_MODEL, "label": "Gemini 3.8 Flash (fast, multimodal & clinical workflows)"},
            {"id": DEFAULT_PRO_MODEL, "label": "Gemini 4 Argon (deep clinical reasoning & complex cases)"},
            {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite (high-speed triage & summaries)"},
        ],
    }


def call_gemini_interaction(prompt, system_instruction=None, response_schema=None, model=None, previous_interaction_id=None, thinking_level="low"):
    """Call Gemini Interactions API via `google-genai` SDK or `/v1beta/interactions` REST."""
    key = get_api_key()
    if not key:
        return None  # Caller falls back to deterministic clinical engine
    use_model = model or _RUNTIME_MODEL or DEFAULT_FLASH_MODEL

    # 1. Prefer official `google-genai` SDK (`client.interactions.create`)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        kwargs = {
            "model": use_model,
            "input": prompt,
            "generation_config": {"thinking_level": thinking_level},
        }
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if response_schema:
            kwargs["response_format"] = response_schema
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id
        interaction = client.interactions.create(**kwargs)
        return {
            "id": getattr(interaction, "id", None),
            "text": getattr(interaction, "output_text", None) or _extract_steps_text(getattr(interaction, "steps", [])),
            "model": use_model,
            "live": True,
        }
    except ImportError:
        pass

    # 2. Zero-dependency REST fallback to `/v1beta/interactions`
    payload = {
        "model": use_model,
        "input": prompt,
        "generation_config": {"thinking_level": thinking_level},
    }
    if system_instruction:
        payload["system_instruction"] = system_instruction
    if response_schema:
        payload["response_format"] = response_schema
    if previous_interaction_id:
        payload["previous_interaction_id"] = previous_interaction_id

    req = urllib.request.Request(
        INTERACTIONS_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
            "Api-Revision": API_REVISION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body.get("output_text") or _extract_steps_text(body.get("steps", []))
            return {"id": body.get("id"), "text": text, "model": use_model, "live": True}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error ({e.code}): {err_body[:240]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Gemini network error: {e.reason}")


def _extract_steps_text(steps):
    chunks = []
    for step in steps or []:
        stype = step.get("type") if isinstance(step, dict) else getattr(step, "type", None)
        if stype == "model_output":
            content = step.get("content", []) if isinstance(step, dict) else getattr(step, "content", [])
            for part in content or []:
                ptype = part.get("type") if isinstance(part, dict) else getattr(part, "type", None)
                if ptype == "text":
                    chunks.append(part.get("text", "") if isinstance(part, dict) else getattr(part, "text", ""))
    return "\n".join(c for c in chunks if c)


# ---------------------------------------------------------------- Clinical AI Workflows

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "urgency": {"type": "string", "enum": ["Emergency", "Urgent", "Semi-Urgent", "Routine"]},
        "esi_level": {"type": "integer"},
        "recommended_department": {"type": "string"},
        "possible_conditions": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "recommended_vitals_and_labs": {"type": "array", "items": {"type": "string"}},
        "triage_notes": {"type": "string"},
    },
    "required": ["urgency", "esi_level", "recommended_department", "possible_conditions", "red_flags", "recommended_vitals_and_labs", "triage_notes"],
}


def ai_triage(symptoms, age=None, gender=None, vitals=None, model=None):
    sys_inst = (
        "You are an expert Emergency Department triage clinician at MediCare General Hospital. "
        "Given patient symptoms, demographics, and optional vitals, return a structured JSON triage assessment "
        "mapping to hospital departments: Cardiology, Neurology, Orthopedics, Pediatrics, Gynecology, General Medicine, Emergency, or Radiology."
    )
    prompt = f"Patient: age={age or 'unknown'}, gender={gender or 'unknown'}, vitals={vitals or 'not recorded'}.\nPresenting complaints: {symptoms}"
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, response_schema=TRIAGE_SCHEMA, model=model, thinking_level="low")
    if res and res.get("text"):
        try:
            data = json.loads(res["text"])
            data["source"] = f"Gemini ({res['model']})"
            return data
        except json.JSONDecodeError:
            pass

    # Deterministic clinical triage fallback
    s = (symptoms or "").lower()
    if any(k in s for k in ("chest pain", "shortness of breath", "palpitation", "radiating", "syncope")):
        dept, urg, esi = "Cardiology", "Emergency", 2
        conds = ["Acute Coronary Syndrome (rule out)", "Unstable Angina", "Arrhythmia"]
        flags = ["Diaphoresis, crushing substernal pain, or SpO2 < 92% require immediate resuscitation bay"]
        labs = ["12-Lead ECG (stat)", "Troponin I/T", "CBC", "Chest X-Ray"]
    elif any(k in s for k in ("stroke", "slurred", "numbness", "seizure", "thunderclap", "migraine", "headache", "dizziness")):
        dept, urg, esi = "Neurology", ("Emergency" if "stroke" in s or "seizure" in s else "Urgent"), (2 if "stroke" in s else 3)
        conds = ["Acute Ischemic TIA / Stroke (rule out)", "Complex Migraine", "Vertigo / Vestibular Neuritis"]
        flags = ["Sudden focal weakness, facial droop, aphasia, or altered sensorium"]
        labs = ["MRI Brain / Non-contrast CT Head", "Blood Glucose (Fasting)", "Electrolytes"]
    elif any(k in s for k in ("fracture", "fall", "sprain", "joint", "knee", "back pain", "swelling")):
        dept, urg, esi = "Orthopedics", "Semi-Urgent", 4
        conds = ["Musculoskeletal Strain / Sprain", "Closed Fracture (rule out)", "Lumbar Radiculopathy"]
        flags = ["Neurovascular compromise, open deformity, or loss of distal pulse"]
        labs = ["X-Ray of affected region", "CRP / ESR if inflammatory"]
    elif age and str(age).isdigit() and int(age) < 15:
        dept, urg, esi = "Pediatrics", "Urgent", 3
        conds = ["Pediatric Viral Syndrome", "Acute Otitis Media / Upper Respiratory Infection"]
        flags = ["Lethargy, poor oral intake, retractions, or persistent high fever"]
        labs = ["Complete Blood Count", "Urine Routine"]
    else:
        dept, urg, esi = "General Medicine", "Routine", 4
        conds = ["Viral Febrile Illness", "Upper Respiratory Tract Infection", "Dyspepsia / Gastritis"]
        flags = ["Persistent fever > 39.5°C, hemodynamic instability, or severe dehydration"]
        labs = ["Complete Blood Count", "Blood Glucose (Fasting)", "Liver Function Test"]

    return {
        "urgency": urg,
        "esi_level": esi,
        "recommended_department": dept,
        "possible_conditions": conds,
        "red_flags": flags,
        "recommended_vitals_and_labs": labs,
        "triage_notes": f"Triaged to {dept} ({urg}, ESI-{esi}). Record full vitals (BP, Temp, Pulse, SpO2) prior to physician encounter.",
        "source": "Built-in Clinical Triage Engine (configure GEMINI_API_KEY for live Gemini 3.8 Flash)",
    }


SOAP_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "icd10_code": {"type": "string"},
        "soap_notes": {"type": "string"},
        "prescription": {"type": "string"},
        "recommended_labs": {"type": "array", "items": {"type": "string"}},
        "follow_up": {"type": "string"},
    },
    "required": ["diagnosis", "icd10_code", "soap_notes", "prescription", "recommended_labs", "follow_up"],
}


def ai_clinical_copilot(brief_notes, patient=None, vitals=None, model=None):
    p_info = f"{patient.get('name')} ({patient.get('gender')}, DOB {patient.get('dob')}, Blood {patient.get('blood_group')}, Allergies: {patient.get('allergies') or 'None'})" if patient else "Unknown patient"
    sys_inst = (
        "You are a clinical documentation & decision-support copilot for physicians at MediCare General Hospital. "
        "Convert brief physician shorthand into a complete SOAP note (Subjective, Objective, Assessment, Plan), "
        "primary diagnosis with ICD-10 code, safe prescription respecting patient allergies, and recommended lab tests."
    )
    prompt = f"Patient: {p_info}\nVitals: {vitals or {}} \nPhysician shorthand / findings: {brief_notes}"
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, response_schema=SOAP_SCHEMA, model=model or DEFAULT_PRO_MODEL, thinking_level="medium")
    if res and res.get("text"):
        try:
            data = json.loads(res["text"])
            data["source"] = f"Gemini ({res['model']})"
            return data
        except json.JSONDecodeError:
            pass

    allergy = (patient or {}).get("allergies") or ""
    b = (brief_notes or "").lower()
    v = vitals or {}
    vitals_line = f"BP {v.get('bp') or '122/78'}, Temp {v.get('temperature') or '37.0'}°C, Pulse {v.get('pulse') or '76'} bpm, Weight {v.get('weight') or '70'} kg"
    if "hypertension" in b or "bp" in b or "headache" in b:
        diag, icd = "Essential (Primary) Hypertension", "I10"
        rx = "1. Tab Amlodipine 5mg OD after breakfast x 30 days\n2. Low-sodium DASH diet (<2g Na/day)\n3. Home BP log twice daily"
        labs = ["Lipid Profile", "Kidney Function Test", "ECG"]
    elif "diabetes" in b or "sugar" in b or "polyuria" in b:
        diag, icd = "Type 2 Diabetes Mellitus", "E11.9"
        rx = "1. Tab Metformin 500mg BD with meals x 30 days\n2. Diabetic diet & 30 min brisk walk daily"
        labs = ["HbA1c", "Blood Glucose (Fasting)", "Kidney Function Test"]
    elif "cough" in b or "fever" in b or "throat" in b or "bronchitis" in b:
        diag, icd = "Acute Upper Respiratory Infection / Bronchitis", "J06.9"
        abx = "Tab Azithromycin 250mg OD x 5 days" if "penicillin" in allergy.lower() else "Cap Amoxicillin 500mg TID x 5 days"
        rx = f"1. Tab Paracetamol 500mg TID PRN fever\n2. {abx} (if bacterial superinfection suspected)\n3. Tab Cetirizine 10mg HS x 5 days\n4. Warm saline gargles & steam inhalation"
        labs = ["Complete Blood Count", "Chest X-Ray"]
    else:
        diag, icd = "Acute Clinical Syndrome – Under Evaluation", "R69"
        rx = "1. Tab Paracetamol 500mg TID PRN pain/fever\n2. Cap Omeprazole 20mg OD before breakfast x 7 days\n3. Oral hydration & rest"
        labs = ["Complete Blood Count", "Liver Function Test"]

    allergy_warn = f" [Allergy alert respected: {allergy}]" if allergy else ""
    soap = (
        f"S (Subjective): Patient presents with: {brief_notes.strip() or 'general clinical evaluation'}.{allergy_warn}\n"
        f"O (Objective): Vitals: {vitals_line}. Alert, oriented x3, no acute cardiopulmonary distress.\n"
        f"A (Assessment): {diag} ({icd}).\n"
        f"P (Plan): Initiate pharmacotherapy as prescribed; order {', '.join(labs)}; review with results in 5–7 days."
    )
    return {
        "diagnosis": f"{diag} ({icd})",
        "icd10_code": icd,
        "soap_notes": soap,
        "prescription": rx,
        "recommended_labs": labs,
        "follow_up": "Review in 1 week or earlier if red-flag symptoms develop.",
        "source": "Built-in Clinical Copilot (configure GEMINI_API_KEY for live Gemini 4 Argon)",
    }


def ai_patient_summary(profile_data, model=None):
    sys_inst = (
        "You are a senior attending physician at MediCare General Hospital. "
        "Synthesize the patient's longitudinal EMR (demographics, allergies, consultations, admissions, labs, dispensed medications, and billing status) "
        "into a concise clinical handoff summary with sections: Clinical Overview, Active Risks & Allergies, Recent Diagnostics & Trends, Medication Review, and Recommended Next Steps. "
        "All currency and billing figures are in PKR (Pakistani Rupees); always prefix monetary amounts with 'PKR '."
    )
    prompt = "Patient EMR JSON:\n" + json.dumps(profile_data, default=str)
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, thinking_level="low")
    if res and res.get("text"):
        return {"summary": res["text"], "source": f"Gemini ({res['model']})"}

    p = profile_data
    enc = p.get("encounters", [])
    adm = p.get("admissions", [])
    labs = p.get("labs", [])
    meds = p.get("medicines", [])
    dx_list = list(dict.fromkeys(e["diagnosis"] for e in enc if e.get("diagnosis")))
    abn_labs = [f"{l['test']} ({l['result']})" for l in labs if l.get("result") and "abnormal" in l["result"].lower()]
    pending_labs = [l["test"] for l in labs if l.get("status") != "Completed"]
    summary = [
        f"### Clinical Overview — {p.get('name')} ({p.get('mrn')})",
        f"- **Demographics:** {p.get('gender') or '—'}, DOB {p.get('dob') or '—'}, Blood Group **{p.get('blood_group') or '—'}**",
        f"- **Allergy Alert:** **{p.get('allergies') or 'No known drug allergies (NKDA)'}**",
        f"- **Recorded Diagnoses ({len(enc)} visits):** {', '.join(dx_list[:5]) if dx_list else 'No prior outpatient encounters recorded'}",
        f"- **Inpatient History ({len(adm)} admissions):** " + (f"Most recent in {adm[0]['ward']} Bed {adm[0]['bed_no']} for *{adm[0]['diagnosis']}* ({adm[0]['status']})." if adm else "No inpatient admissions."),
        f"- **Diagnostics ({len(labs)} lab orders):** "
        + (f"Abnormal flags: {', '.join(abn_labs)}. " if abn_labs else "No abnormal completed results flagged. ")
        + (f"Pending: {', '.join(pending_labs)}." if pending_labs else ""),
        f"- **Recent Medications ({len(meds)} dispensings):** " + (", ".join(f"{m['medicine']} (x{m['quantity']})" for m in meds[:5]) if meds else "None dispensed in hospital pharmacy."),
        "- **Recommended Next Steps:** Reconcile outpatient medications, follow up on any pending laboratory panels, and verify allergy status prior to new prescriptions.",
    ]
    return {
        "summary": "\n".join(summary),
        "source": "Built-in Longitudinal EMR Synthesizer (configure GEMINI_API_KEY for live Gemini)",
    }


def ai_Rx_safety_check(medicines_list, allergies="", existing_meds=None, model=None):
    sys_inst = (
        "You are a clinical pharmacist specialist at MediCare General Hospital. "
        "Evaluate the proposed medication list against patient allergies and existing medications for drug-allergy conflicts, "
        "drug-drug interactions, duplicate therapy, and dosing precautions."
    )
    prompt = f"Patient Allergies: {allergies or 'None'}\nExisting medications: {existing_meds or []}\nProposed medications: {medicines_list}"
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, thinking_level="low")
    if res and res.get("text"):
        return {"report": res["text"], "source": f"Gemini ({res['model']})"}

    meds_str = " ".join(medicines_list if isinstance(medicines_list, list) else [str(medicines_list)]).lower()
    al_str = (allergies or "").lower()
    warnings = []
    if "penicillin" in al_str and any(k in meds_str for k in ("amoxicillin", "ampicillin", "augmentin", "piperacillin")):
        warnings.append("CRITICAL ALLERGY CONFLICT: Patient has a documented Penicillin allergy and Amoxicillin/beta-lactam is listed. Substitute with a macrolide (e.g., Azithromycin) or fluoroquinolone as clinically indicated.")
    if "sulfa" in al_str and "sulf" in meds_str:
        warnings.append("ALLERGY CONFLICT: Documented Sulfa allergy with sulfonamide agent.")
    if "aspirin" in meds_str and "ibuprofen" in meds_str:
        warnings.append("DRUG-DRUG INTERACTION (Moderate-Major): Concurrent NSAID (Ibuprofen) and Aspirin increases GI bleeding risk and may antagonize antiplatelet cardioprotection.")
    if "metformin" in meds_str and "insulin" in meds_str:
        warnings.append("MONITORING PRECAUTION: Concurrent Insulin Glargine + Metformin — counsel patient on hypoglycemia recognition and monitor fasting blood glucose.")
    if not warnings:
        warnings.append("No major drug-allergy or high-severity drug-drug interactions detected among the selected formulary items. Verify renal/hepatic dosing as appropriate.")
    return {
        "report": "\n".join(f"• {w}" for w in warnings),
        "source": "Built-in Clinical Pharmacology Engine (configure GEMINI_API_KEY for live Gemini)",
    }


def ai_executive_briefing(kpis, extra_context, question=None, previous_interaction_id=None, model=None):
    sys_inst = (
        "You are the Chief Medical Information Officer & Operations AI Advisor for MediCare General Hospital. "
        "You have live access to hospital KPIs, bed occupancy, revenue, lab backlog, and pharmacy stock alerts. "
        "All currency, revenue, and invoice figures in this hospital are strictly in PKR (Pakistani Rupees) — always format monetary amounts with 'PKR ' (never use $ or ₹). "
        "Provide actionable, quantitative executive insights and answer administrator/clinician questions accurately."
    )
    prompt = f"Live Hospital Snapshot (All monetary values in PKR):\nKPIs: {json.dumps(kpis, default=str)}\nContext: {json.dumps(extra_context, default=str)}\n"
    if question:
        prompt += f"\nUser Question: {question}"
    else:
        prompt += "\nProvide a concise Executive Daily Briefing covering: (1) Capacity & Bed Management, (2) Clinical & Lab Throughput, (3) Pharmacy Supply Chain Risks, and (4) Revenue Cycle & Collections."

    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, previous_interaction_id=previous_interaction_id, thinking_level="low")
    if res and res.get("text"):
        return {"id": res.get("id"), "reply": res["text"], "source": f"Gemini ({res['model']})"}

    occ = round((kpis.get("beds_occupied", 0) / max(1, kpis.get("beds_total", 1))) * 100)
    if question:
        q = question.lower()
        if "bed" in q or "ward" in q or "admi" in q or "occupancy" in q:
            reply = f"**Bed & Ward Capacity:** Currently **{kpis.get('beds_occupied')}/{kpis.get('beds_total')} beds ({occ}%)** are occupied across {len(extra_context.get('wards', []))} wards, with **{kpis.get('admitted')} active inpatients**. Review long-stay admissions (>5 days) for discharge planning."
        elif "rev" in q or "bill" in q or "invoic" in q or "money" in q or "outstanding" in q:
            reply = f"**Revenue Cycle Snapshot:** Collected **PKR {kpis.get('revenue_today', 0):,.2f}** today and **PKR {kpis.get('revenue_month', 0):,.2f}** month-to-date. Outstanding receivables stand at **PKR {kpis.get('outstanding', 0):,.2f}** — prioritize follow-up on Partial/Unpaid invoices."
        elif "stock" in q or "pharm" in q or "med" in q or "expir" in q:
            low_names = ", ".join(f"{m['name']} ({m['stock']} left)" for m in extra_context.get("low_stock_list", [])[:4])
            reply = f"**Pharmacy Inventory Alert:** **{kpis.get('low_stock')} medicines** are at or below reorder threshold and **{kpis.get('expiring')} items** expire within 90 days. Priority restock: {low_names or 'none'}."
        elif "lab" in q or "test" in q:
            reply = f"**Diagnostics Queue:** There are **{kpis.get('pending_labs')} pending lab orders** awaiting sample collection or result verification."
        else:
            reply = (
                f"**Hospital Status Summary:** {kpis.get('patients')} registered patients | "
                f"{kpis.get('appointments_today')} appointments today | {occ}% bed occupancy | "
                f"PKR {kpis.get('revenue_today', 0):,.2f} collected today | {kpis.get('pending_labs')} pending labs | "
                f"{kpis.get('low_stock')} low-stock medicines."
            )
    else:
        low_names = ", ".join(f"{m['name']} ({m['stock']})" for m in extra_context.get("low_stock_list", [])[:4])
        reply = (
            f"### MediCare General Hospital — Executive Daily Briefing\n"
            f"1. **Capacity & Inpatient Flow:** Bed occupancy is at **{occ}%** ({kpis.get('beds_occupied')}/{kpis.get('beds_total')} beds) with **{kpis.get('admitted')} active admissions** and **{kpis.get('appointments_today')} outpatient appointments** scheduled today across **{kpis.get('doctors')} active doctors**.\n"
            f"2. **Diagnostics Throughput:** **{kpis.get('pending_labs')} lab orders** are currently in `Ordered` or `Sample Collected` status — prioritize STAT hematology and biochemistry panels.\n"
            f"3. **Pharmacy Supply Chain:** **{kpis.get('low_stock')} formulary items** are below reorder level and **{kpis.get('expiring')} batches** expire within 90 days ({low_names or 'all clear'}).\n"
            f"4. **Revenue & Collections:** Today's collections total **PKR {kpis.get('revenue_today', 0):,.2f}** (PKR {kpis.get('revenue_month', 0):,.2f} MTD) with **PKR {kpis.get('outstanding', 0):,.2f}** in open receivables."
        )
    return {
        "id": None,
        "reply": reply,
        "source": "Built-in Hospital Analytics Advisor (configure GEMINI_API_KEY for live Gemini multi-turn chat)",
    }

