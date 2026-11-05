# VizMedCare HMS — Full-Stack Hospital Management System (MVC + Gemini AI Hub)

A full-stack, white-label Hospital Management System built with a **Python MVC REST backend + SQLite relational database** and an **interactive Single-Page Web Application (HTML5 / CSS3 / Vanilla JS + Canvas Charts + Multi-Theme Switcher)**.

---

## Quick Start

```bash
git clone https://github.com/ha242204372/hospital-management-system.git
cd hospital-management-system
python3 server.py
```

The server binds to `0.0.0.0:8000` and displays both local and LAN URLs:
- **On this computer**: `http://localhost:8000`
- **From any device on the same Wi-Fi / Hospital LAN**: `http://<your-lan-ip>:8000`

To reset and re-seed the database with fresh demo data:
```bash
python3 server.py --reset
```

---

## Project MVC Directory Structure

```text
hospital-management-system/
├── server.py                        # HTTP entry point, router & static asset server
├── gemini_ai.py                     # Gemini Interactions API client + built-in clinical engine
├── app/
│   ├── config.py                    # Paths, roles, constants & ApiError
│   ├── models/
│   │   ├── db.py                    # SQLite connection, schema DDL, settings & billing helpers
│   │   ├── schema_registry.py       # Resource metadata (RES) & reference queries (REFS)
│   │   └── seed.py                  # Demo data seeding & migration
│   ├── controllers/
│   │   ├── auth_controller.py       # PBKDF2-HMAC-SHA256 hashing & HTTP session store
│   │   ├── crud_controller.py       # Generic CRUD, validation & clinical auto-billing hooks
│   │   ├── analytics_controller.py  # Dashboard KPIs, 30-day Reports, 360° Profile & Invoices
│   │   ├── settings_controller.py   # Multi-Hospital White-Label Setup & Master Data Onboarding
│   │   ├── ai_controller.py         # Gemini AI Hub routes (/api/ai/*)
│   │   └── db_controller.py         # Database Studio routes (/api/db/*)
│   └── views/
│       ├── templates/index.html     # Main SPA HTML shell
│       └── static/
│           ├── css/style.css        # Multi-theme stylesheet (5 color themes)
│           └── js/app.js            # Frontend SPA, modals, canvas charts & print views
├── database/
│   └── hospital.db                  # SQLite relational database (16 tables)
├── tests/
│   └── e2e.py                       # 39-test automated end-to-end test suite
├── Dockerfile                       # Container image definition
├── render.yaml                      # 1-click Render.com cloud deployment spec
└── Procfile                         # Railway / Heroku process spec
```

---

## Demo Accounts (Role-Based Access Control)

| Role | Username | Password | Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full access to all 15 modules, **Hospital Setup & Master Data**, Database Studio, Reports, Staff, Users & Audit Logs |
| **Doctor** | `doctor` | `doctor123` | Patient 360° EHR charts, appointments, consultations/EMR (SOAP Copilot + Print Rx), admissions & lab orders |
| **Nurse** | `nurse` | `nurse123` | Patients, appointments, vitals/consultations, admissions, visual ward & bed floor map |
| **Receptionist** | `reception` | `reception123` | Patient registration, appointments, admissions, billing & invoicing |
| **Pharmacist** | `pharmacy` | `pharmacy123` | Medicine inventory, 1-click restock, stock/expiry alerts & prescription dispensing |
| **Lab Technician** | `lab` | `lab123` | Lab test catalog, 1-click sample collection & result entry |
| **Accountant** | `accounts` | `accounts123` | Billing, invoices, payment recording (PKR) & 30-day financial analytics |
| **Patient** | `patient` | `patient123` | Patient portal: view own medical profile, appointments, consultations, labs & invoices |

---

## Core Modules & End-to-End Workflows

1. **⚙️ Multi-Hospital White-Label Setup & Master Data (`#settings`)**
   - Configure **Hospital Name, Tagline, Logo Symbol, Currency (`PKR` default, or `USD`, `AED`, `SAR`, `GBP`, `EUR`), Default Color Theme, Patient MRN Prefix, Invoice Prefix, Tax/NTN Number, Address, Phone, and Printable Invoice Footer**.
   - Includes **1-Click Hospital Profile Presets** (*VizMedCare*, *Al-Shifa International Hospital*, *City Care & Trauma Center*, *Noor Mother & Child Specialist Hospital*).
   - **Master Data Onboarding Tabs**:
     - **Doctors & Staff Quick-Add**: Add doctors/staff with consultation fees, auto-create departments, and create their login username/password in one step.
     - **Wards & Auto-Bed Generator**: Create a ward and auto-generate `1..N` numbered beds (e.g. `SW-01`..`SW-08`) in one click.
     - **Departments, Lab Test Tariffs & Pharmacy Formulary** master tables.
   - **🚀 Go-Live Clean Slate Mode**: Clears demo patients/transactions while preserving all configured Master Data so a real hospital can go live immediately.
2. **📊 Executive Dashboard & 30-Day Reports (`#dashboard`, `#reports`)**
   - Quick-Action bar, 8 real-time KPI cards, HTML5 Canvas bar/line/donut charts, and doctor workload analytics.
3. **🧑‍🤝‍🧑 Patient Registration & 360° Longitudinal EHR (`#patients`, `#encounters`)**
   - Automatic MRN generation (`MRN00001`+ or custom hospital prefix).
   - **360° Patient Chart** with 1-click action buttons (**+ Appointment, + Consultation, + Admit, + Lab Order, + Dispense**), **✨ Gemini AI EMR Summary**, and **🖨 Print Clinical Chart**.
   - **Consultations (EMR)** auto-bills the attending doctor's consultation fee, completes today's scheduled appointment, and includes **🖨 Print Rx** for branded medical prescriptions.
4. **🛏️ Visual Ward & Bed Floor Map + IPD Admissions (`#wards`, `#beds`, `#admissions`)**
   - Interactive color-coded bed tiles (`Available`, `Occupied` with patient name, `Maintenance`) with 1-click status toggle and automatic daily bed-charge billing on discharge.
5. **🔬 Diagnostics & Laboratory (`#lab_orders`, `#lab_tests`)**
   - 1-click workflow progression (`Ordered` -> `🧪 Collect Sample` -> `📝 Enter Result`) with automatic patient billing.
6. **💊 Pharmacy & Inventory (`#medicines`, `#dispensing`)**
   - Low-stock and ≤90-day expiry row highlighting, 1-click **＋ Restock**, and stock-validated dispensing with automatic billing.
7. **💳 Billing, Invoicing & Payments (`#invoices`)**
   - Auto-aggregated open invoices per patient in **PKR**, custom line items, partial/full payments, overpayment protection, and hospital-branded printable invoices.
8. **✨ Gemini AI Clinical & Operations Hub (`#gemini_ai`)**
   - **AI Symptom Triage & ESI Acuity**, **Physician SOAP Note & ICD-10 Copilot**, **Longitudinal EMR Synthesizer**, **Pharmacy Drug-Allergy & Interaction Checker**, and **Stateful Executive Briefing & Q&A** (with persistent `.env` API key storage).
9. **🗄️ Database Studio & SQLite Inspector (`#db_studio`)**
   - Inspect all relational tables, run read-only `SELECT` / `PRAGMA` queries, download a live `.db` backup, or re-seed demo data.

---

## Running Automated End-to-End Tests

```bash
python3 tests/e2e.py
```
Runs 39 end-to-end assertions covering authentication, RBAC, clinical auto-billing, pharmacy stock locks, bed double-booking protection, Gemini AI endpoints, Database Studio, and Multi-Hospital White-Label Setup.
