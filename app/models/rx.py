"""Prescription module schema and Pakistani drug seed. Additive only."""
from datetime import date

DRUGS = [
    ("Paracetamol", "Panadol", "500mg", "tab", "Oral", "Analgesic", "1 tab", 15),
    ("Paracetamol", "Calpol", "250mg/5ml", "syp", "Oral", "Analgesic", "5 ml", 80),
    ("Ibuprofen", "Brufen", "400mg", "tab", "Oral", "NSAID", "1 tab", 25),
    ("Diclofenac", "Voltral", "50mg", "tab", "Oral", "NSAID", "1 tab", 20),
    ("Naproxen", "Synflex", "250mg", "tab", "Oral", "NSAID", "1 tab", 30),
    ("Amoxicillin", "Amoxil", "500mg", "cap", "Oral", "Antibiotic", "1 cap", 40),
    ("Amoxicillin+Clavulanate", "Augmentin", "625mg", "tab", "Oral", "Antibiotic", "1 tab", 90),
    ("Azithromycin", "Zithromax", "250mg", "tab", "Oral", "Antibiotic", "1 tab", 70),
    ("Ciprofloxacin", "Ciproxin", "500mg", "tab", "Oral", "Antibiotic", "1 tab", 45),
    ("Levofloxacin", "Leflox", "500mg", "tab", "Oral", "Antibiotic", "1 tab", 55),
    ("Metronidazole", "Flagyl", "400mg", "tab", "Oral", "Antibiotic", "1 tab", 20),
    ("Cefixime", "Cefspan", "400mg", "cap", "Oral", "Antibiotic", "1 cap", 85),
    ("Ceftriaxone", "Rocephin", "1g", "inj", "IV", "Antibiotic", "1 vial", 180),
    ("Omeprazole", "Risek", "20mg", "cap", "Oral", "PPI", "1 cap", 35),
    ("Esomeprazole", "Nexum", "40mg", "tab", "Oral", "PPI", "1 tab", 50),
    ("Pantoprazole", "Pantocid", "40mg", "tab", "Oral", "PPI", "1 tab", 40),
    ("Domperidone", "Motilium", "10mg", "tab", "Oral", "Antiemetic", "1 tab", 18),
    ("Ondansetron", "Zofran", "8mg", "tab", "Oral", "Antiemetic", "1 tab", 60),
    ("Metformin", "Glucophage", "500mg", "tab", "Oral", "Antidiabetic", "1 tab", 12),
    ("Gliclazide", "Diamicron", "80mg", "tab", "Oral", "Antidiabetic", "1 tab", 28),
    ("Sitagliptin", "Januvia", "100mg", "tab", "Oral", "Antidiabetic", "1 tab", 120),
    ("Amlodipine", "Norvasc", "5mg", "tab", "Oral", "Antihypertensive", "1 tab", 15),
    ("Losartan", "Cozaar", "50mg", "tab", "Oral", "Antihypertensive", "1 tab", 22),
    ("Atenolol", "Tenormin", "50mg", "tab", "Oral", "Antihypertensive", "1 tab", 14),
    ("Ramipril", "Tritace", "5mg", "tab", "Oral", "Antihypertensive", "1 tab", 30),
    ("Atorvastatin", "Lipitor", "10mg", "tab", "Oral", "Statin", "1 tab", 35),
    ("Rosuvastatin", "Crestor", "10mg", "tab", "Oral", "Statin", "1 tab", 45),
    ("Aspirin", "Disprin", "75mg", "tab", "Oral", "Antiplatelet", "1 tab", 8),
    ("Clopidogrel", "Plavix", "75mg", "tab", "Oral", "Antiplatelet", "1 tab", 40),
    ("Cetirizine", "Zyrtec", "10mg", "tab", "Oral", "Antihistamine", "1 tab", 10),
    ("Loratadine", "Clarityne", "10mg", "tab", "Oral", "Antihistamine", "1 tab", 12),
    ("Montelukast", "Singulair", "10mg", "tab", "Oral", "Antiasthmatic", "1 tab", 38),
    ("Salbutamol", "Ventolin", "100mcg", "inh", "Inhaled", "Bronchodilator", "2 puffs", 150),
    ("Prednisolone", "Deltacortril", "5mg", "tab", "Oral", "Steroid", "1 tab", 8),
    ("Dexamethasone", "Decadron", "4mg", "tab", "Oral", "Steroid", "1 tab", 10),
    ("ORS", "Pedialyte", "sachet", "sachet", "Oral", "Rehydration", "1 sachet", 15),
    ("Zinc", "Zincat", "20mg", "tab", "Oral", "Supplement", "1 tab", 8),
    ("Vitamin D", "Calcirol", "200000 IU", "sachet", "Oral", "Supplement", "1 sachet", 40),
    ("Iron+Folic", "Fefol", "cap", "cap", "Oral", "Supplement", "1 cap", 18),
    ("Calcium", "Ossopan", "500mg", "tab", "Oral", "Supplement", "1 tab", 12),
    ("Tramadol", "Tramal", "50mg", "cap", "Oral", "Analgesic", "1 cap", 35),
    ("Alprazolam", "Xanax", "0.5mg", "tab", "Oral", "Anxiolytic", "1 tab", 20),
    ("Diazepam", "Valium", "5mg", "tab", "Oral", "Anxiolytic", "1 tab", 12),
    ("Fluconazole", "Diflucan", "150mg", "cap", "Oral", "Antifungal", "1 cap", 50),
    ("Clotrimazole", "Canesten", "1%", "cream", "Topical", "Antifungal", "apply", 90),
    ("Chlorpheniramine", "Piriton", "4mg", "tab", "Oral", "Antihistamine", "1 tab", 6),
    ("Hyoscine", "Buscopan", "10mg", "tab", "Oral", "Antispasmodic", "1 tab", 15),
    ("Loperamide", "Imodium", "2mg", "cap", "Oral", "Antidiarrheal", "1 cap", 12),
    ("Lactulose", "Duphalac", "3.35g/5ml", "syp", "Oral", "Laxative", "15 ml", 120),
    ("Insulin regular", "Actrapid", "100 IU/ml", "inj", "SC", "Antidiabetic", "as advised", 450),
]

TEMPLATES = [
    ("Adult URTI", "Upper respiratory infection", [("Paracetamol", "1 tab", "TDS", "3 days"), ("Cetirizine", "1 tab", "OD", "5 days"), ("Azithromycin", "1 tab", "OD", "3 days")]),
    ("Adult fever", "Fever", [("Paracetamol", "1 tab", "TDS", "3 days"), ("ORS", "1 sachet", "TDS", "2 days")]),
    ("Gastritis", "Gastritis", [("Omeprazole", "1 cap", "OD", "14 days"), ("Domperidone", "1 tab", "TDS", "5 days")]),
    ("UTI", "Urinary tract infection", [("Ciprofloxacin", "1 tab", "BD", "5 days"), ("Paracetamol", "1 tab", "TDS", "3 days")]),
    ("Hypertension starter", "Hypertension", [("Amlodipine", "1 tab", "OD", "30 days"), ("Aspirin", "1 tab", "OD", "30 days")]),
]


def ensure_rx_tables(conn, exec_sql):
    stmts = [
        """CREATE TABLE IF NOT EXISTS drug_master (
            id SERIAL PRIMARY KEY, generic TEXT, brand TEXT, strength TEXT, form TEXT,
            route TEXT, category TEXT, default_dose TEXT, price REAL, controlled INTEGER DEFAULT 0,
            pharmacy_id INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS rx_header (
            id SERIAL PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER, encounter_id INTEGER,
            date TEXT, diagnosis TEXT, notes TEXT, status TEXT DEFAULT 'draft',
            follow_up TEXT, version INTEGER DEFAULT 1, token TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS rx_item (
            id SERIAL PRIMARY KEY, rx_id INTEGER, drug_id INTEGER, dose TEXT, frequency TEXT,
            duration TEXT, quantity INTEGER, route TEXT, timing TEXT, instructions TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS rx_template (
            id SERIAL PRIMARY KEY, doctor_id INTEGER, name TEXT, diagnosis TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS rx_template_item (
            id SERIAL PRIMARY KEY, template_id INTEGER, drug_name TEXT, dose TEXT, frequency TEXT, duration TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS rx_audit (
            id SERIAL PRIMARY KEY, rx_id INTEGER, action TEXT, user_name TEXT, at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS patient_allergy (
            id SERIAL PRIMARY KEY, patient_id INTEGER, substance TEXT, reaction TEXT
        )""",
    ]
    for sql in stmts:
        try:
            exec_sql(conn, sql)
        except Exception:
            pass


def seed_drugs(conn, exec_sql, rows_fn):
    existing = rows_fn(conn, "SELECT COUNT(*) AS n FROM drug_master")
    if existing and existing[0].get("n", 0) > 0:
        return
    for g, b, s, f, r, c, d, p in DRUGS:
        exec_sql(conn, "INSERT INTO drug_master(generic, brand, strength, form, route, category, default_dose, price) VALUES (?,?,?,?,?,?,?,?)",
                 (g, b, s, f, r, c, d, p))
    for name, dx, items in TEMPLATES:
        exec_sql(conn, "INSERT INTO rx_template(name, diagnosis) VALUES (?,?)", (name, dx))
        tid = rows_fn(conn, "SELECT id FROM rx_template WHERE name=? ORDER BY id DESC LIMIT 1", (name,))
        if tid:
            for drug, dose, freq, dur in items:
                exec_sql(conn, "INSERT INTO rx_template_item(template_id, drug_name, dose, frequency, duration) VALUES (?,?,?,?,?)",
                         (tid[0]["id"], drug, dose, freq, dur))
