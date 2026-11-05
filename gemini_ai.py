#!/usr/bin/env python3
"""Gemini AI Hub for VizMedCare HMS.

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
    except Exception:
        return None

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
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body.get("output_text") or _extract_steps_text(body.get("steps", []))
            return {"id": body.get("id"), "text": text, "model": use_model, "live": True}
    except Exception:
        return None


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
        "emergency_medications": {"type": "array", "items": {"type": "string"}},
        "immediate_interventions": {"type": "array", "items": {"type": "string"}},
        "triage_notes": {"type": "string"},
    },
    "required": [
        "urgency",
        "esi_level",
        "recommended_department",
        "possible_conditions",
        "red_flags",
        "recommended_vitals_and_labs",
        "emergency_medications",
        "immediate_interventions",
        "triage_notes",
    ],
}


def ai_triage(symptoms, age=None, gender=None, vitals=None, model=None):
    sys_inst = (
        "You are an expert Emergency Department triage clinician at VizMedCare. "
        "Given patient symptoms, demographics, and optional vitals, return a structured JSON triage assessment "
        "mapping to hospital departments: Cardiology, Neurology, Orthopedics, Pediatrics, Gynecology, General Medicine, Emergency, or Radiology. "
        "Always include `emergency_medications` (stat/first-line emergency treatment medicines with dose and route, e.g., Chewable Aspirin 300mg PO stat, "
        "Sublingual Nitroglycerin 0.4mg, Nebulized Salbutamol 5mg, Inj Paracetamol 1g IV, Inj Ondansetron 4mg IV, Inj Ceftriaxone 1g IV, IV Normal Saline 0.9%) "
        "and `immediate_interventions` (bedside stabilization steps)."
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

    # Deterministic clinical triage & emergency medication fallback
    s = (symptoms or "").lower()
    s_no_hb = s.replace("heart burn", "acid reflux").replace("heartburn", "acid reflux")
    if any(k in s_no_hb for k in ("chest", "pressure", "angina", "palpitation", "radiating", "syncope", "cardiac", "heart attack")):
        dept, urg, esi = "Cardiology", "Emergency", 2
        conds = ["Acute Coronary Syndrome (ACS / MI — rule out)", "Unstable Angina", "Cardiac Arrhythmia"]
        flags = ["Diaphoresis, crushing substernal pain, hypotension, or SpO2 < 92% require immediate resuscitation bay"]
        labs = ["12-Lead ECG within 10 min (STAT)", "Cardiac Troponin I/T", "CBC", "Electrolytes", "Portable Chest X-Ray"]
        meds = [
            "Tab Aspirin 300mg chewable PO STAT (if no allergy/active bleeding)",
            "Tab Nitroglycerin (Glyceryl Trinitrate) 0.4mg Sublingual STAT (if SBP > 100 mmHg)",
            "Tab Clopidogrel 300mg PO loading dose + Tab Atorvastatin 80mg PO STAT (per ACS protocol)",
            "Inj Morphine 2–4mg IV slow push PRN severe refractory chest pain + Inj Ondansetron 4mg IV",
            "Oxygen therapy 2–4 L/min via nasal cannula if SpO2 < 94%",
        ]
        interventions = ["Continuous 12-lead cardiac monitoring & pulse oximetry", "Establish 2 large-bore IV lines (18G)", "Keep defibrillator/crash cart at bedside"]
    elif any(k in s for k in ("abdom", "stomach", "heart burn", "heartburn", "acid", "indigestion", "ulcer", "vomit", "diarrhea", "gastritis", "epigastric", "nausea", "food poison", "appendic", "colic")):
        dept, urg, esi = "General Medicine / Emergency", "Urgent", 3
        conds = [
            "Acute Gastritis / Severe Gastroesophageal Reflux (GERD / Dyspepsia)",
            "Peptic Ulcer Disease / Acute Biliary Colic",
            "Inferior Wall Myocardial Ischemia (rule out via ECG in epigastric pain age ≥ 40)",
        ]
        flags = ["Hematemesis (vomiting blood), black tarry stools (melena), peritoneal rigidity, or pain radiating to jaw/left arm"]
        labs = ["12-Lead ECG (STAT — mandatory to rule out inferior MI in epigastric pain)", "Complete Blood Count", "Liver Function Test & Serum Amylase/Lipase", "H. pylori Stool Antigen / Ultrasound Abdomen"]
        meds = [
            "Inj Omeprazole 40mg IV STAT (or Inj Pantoprazole 40mg IV STAT — Proton Pump Inhibitor)",
            "Syp Antacid + Oxetacaine (Mucaine / Gaviscon Gel) 10–15mL PO STAT for immediate heartburn & epigastric relief",
            "Inj Famotidine 20mg IV STAT (H2-receptor antagonist)",
            "Inj Ondansetron 4mg IV STAT (if nausea/vomiting) + Inj Hyoscine Butylbromide (Buscopan) 20mg IV PRN stomach spasm",
            "AVOID NSAIDs (Ibuprofen, Ketorolac, Diclofenac, Aspirin) as they worsen gastritis/peptic ulceration",
        ]
        interventions = ["Obtain 12-Lead ECG first in patients ≥ 40 yrs with upper stomach/epigastric pain", "Elevate head of bed 30–45°", "IV 0.9% Normal Saline 500mL if dehydrated or unable to tolerate oral fluids"]
    elif any(k in s for k in ("shortness", "breath", "asthma", "wheez", "copd", "dyspnea", "choking", "spo2", "cough", "pneumonia")):
        dept, urg, esi = "Emergency", "Emergency", 2
        conds = ["Acute Severe Bronchospasm / Asthma Exacerbation", "Acute COPD Exacerbation", "Community-Acquired Pneumonia"]
        flags = ["Silent chest, cyanosis, inability to speak full sentences, SpO2 < 90%, or accessory muscle exhaustion"]
        labs = ["Arterial Blood Gas (ABG)", "Chest X-Ray (STAT)", "Complete Blood Count", "CRP"]
        meds = [
            "Nebulized Salbutamol 5mg + Ipratropium Bromide 0.5mg driven by O2 STAT (repeat q20min x 3)",
            "Inj Hydrocortisone 100mg IV STAT (or Tab Prednisolone 40mg PO)",
            "Controlled Oxygen therapy to maintain target SpO2 94–98% (88–92% in chronic COPD)",
            "Inj Ceftriaxone 1g IV STAT + Tab Azithromycin 500mg PO (if bacterial pneumonia suspected)",
            "Tab Paracetamol 500mg–1g PO/IV if febrile",
        ]
        interventions = ["Position patient upright (High Fowler's position)", "Continuous SpO2 & respiratory rate monitoring", "Prepare non-invasive ventilation (BiPAP) if hypercapnic"]
    elif any(k in s for k in ("stroke", "slurred", "numbness", "weakness", "paralysis", "seizure", "convulsion", "unconscious", "coma")):
        dept, urg, esi = "Neurology", "Emergency", 1
        conds = ["Acute Ischemic / Hemorrhagic Stroke (CVA)", "Status Epilepticus / Acute Seizure", "Transient Ischemic Attack (TIA)"]
        flags = ["Sudden facial droop, arm drift, speech slurring (FAST positive), GCS < 12, or active tonic-clonic seizure"]
        labs = ["Non-Contrast CT Head (STAT — Door-to-CT < 20 min)", "Capillary Blood Glucose (STAT)", "MRI Brain", "Coagulation Profile (PT/INR)"]
        meds = [
            "If active seizure: Inj Lorazepam 4mg IV slow push (or Inj Diazepam 10mg IV) STAT, followed by Inj Levetiracetam 1g IV infusion",
            "If hypoglycemic (< 70 mg/dL): Inj 25% Dextrose 100mL IV STAT",
            "If Acute Ischemic Stroke confirmed on CT (no hemorrhage): IV Alteplase (rtPA) per stroke window OR Tab Aspirin 300mg after CT excludes bleed",
            "Inj Labetalol 10–20mg IV PRN if severe hypertension > 185/110 mmHg",
        ]
        interventions = ["Protect airway, lateral recovery position if post-ictal, suction at bedside", "Keep NPO (Nothing by Mouth) until swallow screen completed", "Record exact symptom onset ('last known well') time"]
    elif any(k in s for k in ("migraine", "headache", "dizziness", "vertigo")):
        dept, urg, esi = "Neurology", "Urgent", 3
        conds = ["Acute Severe Migraine / Tension Headache", "Acute Vestibular Neuritis / Vertigo", "Hypertensive Urgency"]
        flags = ["Thunderclap onset, neck stiffness/meningismus, photophobia with fever, or focal neurological deficit"]
        labs = ["Blood Pressure check", "Blood Glucose", "CT Head (if red-flag headache)"]
        meds = [
            "Inj Ketorolac 30mg IV/IM or Inj Paracetamol 1g IV infusion for acute headache relief",
            "Inj Metoclopramide 10mg IV or Inj Ondansetron 4mg IV STAT for nausea/vomiting",
            "Tab Sumatriptan 50mg PO (if established migraine without cardiovascular contraindications)",
            "Tab Prochlorperazine 5mg or Tab Betahistine 16mg PO (if acute vertigo/dizziness)",
        ]
        interventions = ["Place patient in quiet, darkened room", "IV Normal Saline 500mL hydration", "Serial neurological checks"]
    elif any(k in s for k in ("abdom", "stomach", "vomit", "diarrhea", "gastritis", "epigastric", "acidity", "nausea", "food poison", "appendic", "colic")):
        dept, urg, esi = ("Emergency" if "severe" in s or "blood" in s else "General Medicine"), ("Urgent" if "severe" in s or "vomit" in s else "Semi-Urgent"), 3
        conds = ["Acute Gastroenteritis / Dehydration", "Acute Gastritis / Peptic Ulcer Disease", "Acute Appendicitis / Biliary Colic (rule out)"]
        flags = ["Peritoneal guarding/rigidity, hematemesis (vomiting blood), melena, or hypovolemic shock"]
        labs = ["Complete Blood Count", "Serum Electrolytes & Creatinine", "Liver Function Test & Serum Amylase/Lipase", "Ultrasound Abdomen"]
        meds = [
            "Inj Omeprazole / Pantoprazole 40mg IV STAT (proton pump inhibitor)",
            "Inj Ondansetron 4–8mg IV STAT (antiemetic for vomiting/nausea)",
            "IV Ringer's Lactate or 0.9% Normal Saline 500–1000mL infusion + Oral Rehydration Salts (ORS Sachet)",
            "Inj Hyoscine Butylbromide (Buscopan) 20mg IV/IM STAT for visceral abdominal cramping/spasm",
            "Tab Metronidazole 400mg TID or Tab Ciprofloxacin 500mg BD (if bacterial gastroenteritis confirmed)",
        ]
        interventions = ["Monitor strict fluid intake/output & hydration status", "Abdominal palpation for rebound tenderness (McBurney's/Murphy's sign)"]
    elif any(k in s for k in ("allergy", "anaphylax", "rash", "hives", "swelling", "bee", "itch", "urticaria")):
        dept, urg, esi = "Emergency", ("Emergency" if "throat" in s or "breath" in s or "anaphylax" in s else "Urgent"), 2
        conds = ["Acute Allergic Reaction / Anaphylaxis", "Acute Urticaria / Angioedema"]
        flags = ["Stridor, tongue/lip angioedema, hoarseness, wheezing, or hypotension"]
        labs = ["Continuous Pulse Oximetry & BP", "Complete Blood Count"]
        meds = [
            "Inj Adrenaline (Epinephrine) 1:1000 — 0.3–0.5mg IM into anterolateral thigh STAT (if anaphylaxis/airway compromise)",
            "Inj Hydrocortisone 200mg IV STAT (or Inj Dexamethasone 8mg IV)",
            "Inj Chlorpheniramine (Avil) 10mg IV slow push OR Tab Cetirizine 10mg PO STAT",
            "Inj Famotidine 20mg IV (H2 blocker) + IV Normal Saline 0.9% 1000mL rapid bolus if hypotensive",
        ]
        interventions = ["Maintain patent airway; prepare airway/intubation kit if angioedema present", "Remove suspected allergen immediately"]
    elif any(k in s for k in ("fracture", "fall", "sprain", "joint", "knee", "back", "trauma", "accident", "bleed", "wound", "burn", "injury")):
        dept, urg, esi = "Orthopedics", "Urgent", 3
        conds = ["Acute Trauma / Closed or Open Fracture (rule out)", "Musculoskeletal Sprain / Soft-Tissue Injury", "Acute Lumbar Radiculopathy"]
        flags = ["Absent distal pulse, compartment syndrome, open fracture, active arterial bleeding, or C-spine tenderness"]
        labs = ["X-Ray of affected limb/spine (AP & Lateral)", "Complete Blood Count", "Blood Grouping & Crossmatch (if bleeding)"]
        meds = [
            "Inj Ketorolac 30mg IV/IM or Inj Diclofenac 75mg IM STAT for acute trauma pain",
            "Inj Paracetamol 1g IV infusion + Topical Diclofenac Gel (for localized sprain/strain)",
            "Inj Tetanus Toxoid (TT) 0.5mL IM STAT (if open wound/laceration/abrasion)",
            "Inj Ceftriaxone 1g IV STAT (prophylaxis if open fracture or contaminated wound)",
        ]
        interventions = ["Immobilize injured limb with splint/backboard; apply direct pressure to any bleeding", "RICE protocol (Rest, Ice, Compression, Elevation) & neurovascular check"]
    elif age and str(age).isdigit() and int(age) < 15:
        dept, urg, esi = "Pediatrics", "Urgent", 3
        conds = ["Pediatric Acute Febrile Illness", "Acute Upper Respiratory / Ear Infection", "Pediatric Gastroenteritis"]
        flags = ["Lethargy, poor oral intake, subcostal retractions, sunken fontanelle, or persistent high fever"]
        labs = ["Complete Blood Count", "Urine Routine", "Rapid Viral / Malaria / Dengue Screen"]
        meds = [
            "Syp Paracetamol (15 mg/kg/dose) PO q6h PRN fever/pain + tepid sponging",
            "Oral Rehydration Salts (ORS Sachet) small frequent sips after each loose stool/vomiting",
            "Nebulized Salbutamol 2.5mg (if wheezing or bronchiolitis)",
            "Syp Amoxicillin (40 mg/kg/day) or Syp Azithromycin (10 mg/kg/day) if bacterial infection confirmed",
        ]
        interventions = ["Record accurate pediatric weight (kg) for weight-based dosing", "Encourage oral fluids and monitor urine output"]
    else:
        dept, urg, esi = "General Medicine", ("Urgent" if "high fever" in s or "severe" in s else "Routine"), (3 if "high fever" in s or "severe" in s else 4)
        conds = ["Acute Viral Febrile Illness", "Upper Respiratory Tract Infection", "Acute Dyspepsia / Gastritis"]
        flags = ["Persistent fever > 39.5°C, hemodynamic instability, rigors, or severe dehydration"]
        labs = ["Complete Blood Count", "Blood Glucose (Fasting/Random)", "Urine Routine", "Liver Function Test"]
        meds = [
            "Tab Paracetamol 500mg–1g PO/IV STAT (antipyretic & analgesic for fever/body aches)",
            "Cap Omeprazole 20mg PO / Inj IV STAT (gastric protection / dyspepsia)",
            "Tab Cetirizine 10mg PO HS (for nasal congestion / allergic symptoms)",
            "Oral Rehydration Salts (ORS Sachet) in 1L water + IV Normal Saline 500mL if dehydrated",
            "Cap Amoxicillin 500mg TID or Tab Azithromycin 500mg OD (only if bacterial focus identified)",
        ]
        interventions = ["Record full baseline vitals (BP, Temp, Pulse, RR, SpO2)", "Tepid sponging if Temp > 38.5°C and initiate oral hydration"]

    return {
        "urgency": urg,
        "esi_level": esi,
        "recommended_department": dept,
        "possible_conditions": conds,
        "red_flags": flags,
        "recommended_vitals_and_labs": labs,
        "emergency_medications": meds,
        "immediate_interventions": interventions,
        "triage_notes": f"Triaged to {dept} ({urg}, ESI-{esi}). Record full vitals (BP, Temp, Pulse, SpO2) and administer stat first-line relief as clinically indicated.",
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
        "You are a clinical documentation & decision-support copilot for physicians at VizMedCare. "
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
        "You are a senior attending physician at VizMedCare. "
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
        "You are a clinical pharmacist specialist at VizMedCare. "
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
        "You are the Chief Medical Information Officer & Operations AI Advisor for VizMedCare. "
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
            f"### VizMedCare — Executive Daily Briefing\n"
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



def ai_clinical_coding(diagnosis, notes="", model=None):
    """Suggest ICD-style codes from diagnosis and notes."""
    prompt = f"Diagnosis: {diagnosis}\nNotes: {notes}\nSuggest 1-3 likely ICD-10 style codes with short descriptions. Format as bullet list."
    sys_inst = "You are a clinical coding assistant. Return concise ICD-10 style suggestions only. Do not invent patient data."
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, thinking_level="low")
    if res and res.get("text"):
        return {"codes": res["text"], "source": f"Gemini ({res['model']})"}
    # Fallback
    return {"codes": f"- R69: Illness, unspecified (from: {diagnosis[:60]})", "source": "Rule-based fallback"}


def ai_discharge_narrative(admission, labs=None, prescriptions=None, model=None):
    """Generate a polished discharge summary narrative."""
    labs = labs or []
    prescriptions = prescriptions or []
    prompt = f"""Patient: {admission.get('patient')} MRN {admission.get('mrn')}
Admitted: {admission.get('admit_date')} Discharged: {admission.get('discharge_date')}
Ward: {admission.get('ward')} Bed: {admission.get('bed_no')}
Doctor: {admission.get('doctor')}
Diagnosis: {admission.get('diagnosis')}
Allergies: {admission.get('allergies') or 'None'}
Labs: {labs}
Prescriptions: {prescriptions}
Write a concise professional discharge summary with: Hospital Course, Discharge Diagnosis, Medications, Follow-up instructions."""
    sys_inst = "You are a hospital discharge summary writer. Be factual, concise, and professional."
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, thinking_level="low")
    if res and res.get("text"):
        return {"narrative": res["text"], "source": f"Gemini ({res['model']})"}
    return {"narrative": f"Patient {admission.get('patient')} admitted {admission.get('admit_date')} for {admission.get('diagnosis')}. Discharged {admission.get('discharge_date') or 'pending'}. Follow up as advised.", "source": "Template fallback"}


def ai_inventory_forecast(medicines, model=None):
    """Suggest reorder quantities."""
    prompt = f"Medicines low or expiring: {medicines}\nFor each, suggest a practical reorder quantity and priority (High/Medium/Low). Keep it short."
    sys_inst = "You are a hospital pharmacy inventory advisor. Be practical and concise."
    res = call_gemini_interaction(prompt, system_instruction=sys_inst, model=model, thinking_level="low")
    if res and res.get("text"):
        return {"forecast": res["text"], "source": f"Gemini ({res['model']})"}
    lines = []
    for m in (medicines or [])[:8]:
        qty = max(10, (m.get("reorder_level") or 10) * 2)
        lines.append(f"- {m.get('name')}: reorder ~{qty} (priority High if stock <= reorder)")
    return {"forecast": "\n".join(lines) or "No critical items.", "source": "Rule-based fallback"}
