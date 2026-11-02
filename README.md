# MediCare HMS — Full-Stack Hospital Management System

A full-stack, zero-dependency Hospital Management System built with a **Python REST backend + SQLite relational database** and an **interactive Single-Page Web Application (HTML5 / CSS3 / Vanilla JS + Canvas Charts)**.

## Quick Start

```bash
cd /Users/adnansheeraz/.gemini/antigravity/scratch/hospital-management-system
python3 server.py
```

Then open **http://localhost:8000** in your browser.
To reset and re-seed the database with fresh demo data:

```bash
python3 server.py --reset
```

## Demo Accounts (Role-Based Access Control)

| Role | Username | Password | Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full access to all 15 modules, reports, staff, user accounts, and audit logs |
| **Doctor** | `doctor` | `doctor123` | Patient EHR profiles, appointments, consultations/EMR, admissions, lab orders |
| **Nurse** | `nurse` | `nurse123` | Patients, appointments, vitals/consultations, admissions, wards & beds |
| **Receptionist** | `reception` | `reception123` | Patient registration, appointments, admissions, billing & invoicing |
| **Pharmacist** | `pharmacy` | `pharmacy123` | Medicine inventory, stock alerts, and prescription dispensing |
| **Lab Technician** | `lab` | `lab123` | Lab test catalog, sample collection, and test result entry |
| **Accountant** | `accounts` | `accounts123` | Billing, invoices, payment recording, and 30-day financial analytics |
| **Patient** | `patient` | `patient123` | Patient portal: view own medical profile, appointments, consultations, labs, and invoices |

## Core Modules Included

1. **Dashboard & Reports (`dashboard`, `reports`)**
   - Real-time KPI cards (Total Patients, Appointments Today, Bed Occupancy %, Active Doctors, Revenue Collected, Outstanding Balance, Pending Labs, Low-Stock / Expiring Medicines)
   - Interactive HTML5 Canvas bar charts, line charts, donut charts, and horizontal progress bars
   - 30-day financial analytics, top diagnoses, most dispensed medicines, lab utilization, and doctor workload tables
2. **Patient Registration & EHR (`patients`, `encounters`)**
   - Automatic Medical Record Number (`MRN00001`+) generation
   - 360° Patient Profile modal showing demographics, allergies, emergency contacts, consultations, admissions, appointments, lab results, dispensed medicines, and invoices
   - Clinical Consultations (EMR) recording vitals (BP, temperature, pulse, weight), diagnosis, notes, and prescriptions — automatically bills the attending doctor's consultation fee and marks scheduled appointments as `Completed`
3. **Doctor & Staff Management + Scheduling (`departments`, `staff`, `appointments`)**
   - Department directory and multi-role staff roster with consultation fees
   - Appointment scheduling with status tracking (`Scheduled`, `Completed`, `Cancelled`, `No-show`)
4. **Bed / Ward Allocation & Inpatient Admissions (`wards`, `beds`, `admissions`)**
   - Interactive **Visual Ward & Bed Floor Map** with color-coded bed tiles (`Available`, `Occupied` with current patient name, `Maintenance`)
   - Automated bed locking upon admission and automated daily bed-charge billing upon discharge
5. **Diagnostics & Laboratory (`lab_tests`, `lab_orders`)**
   - Lab test catalog with reference ranges and pricing
   - Lab orders workflow (`Ordered` -> `Sample Collected` -> `Completed`) with automatic charge addition to the patient's open invoice
6. **Pharmacy & Inventory (`medicines`, `dispensing`)**
   - Medicine stock tracking with visual low-stock (`dangerrow`) and ≤90-day expiry (`warnrow`) alerts
   - Dispensing workflow that validates stock, decrements inventory, and bills the patient automatically
7. **Billing, Invoicing & Payments (`invoices`, `invoice_items`, `payments`)**
   - Auto-aggregated open invoices per patient + manual line-item charges
   - Partial and full payment recording (`Cash`, `Card`, `UPI`, `Insurance`, `Bank transfer`) with overpayment protection and printable invoice view
8. **Security, Users & Audit Trail (`users`, `audit_log`)**
   - PBKDF2-HMAC-SHA256 salted password hashing, HTTP-only session cookies, role-based access enforcement, and comprehensive audit logging
   - One-click **CSV Export** on every module table
9. **✨ Gemini AI Clinical & Operations Hub (`gemini_ai.py`)**
   - Built on the **Gemini Interactions API** (`client.interactions.create` / `POST /v1beta/interactions` with `Api-Revision: 2026-05-20`) supporting `gemini-3.8-flash`, `gemini-4-argon`, and `gemini-3.5-flash-lite`
   - **AI Symptom Triage & ESI Acuity (`/api/ai/triage`):** Uses structured JSON `response_format` schema to classify urgency (`Emergency`, `Urgent`, `Semi-Urgent`, `Routine`), ESI 1–5 acuity, recommended hospital department, red flags, and stat diagnostic workup
   - **Physician SOAP Note & ICD-10 Copilot (`/api/ai/copilot`):** Embedded directly inside the **New Consultation (EMR)** modal ("✨ Auto-Draft with Gemini") and in the Gemini AI Hub — converts brief shorthand + vitals into a full SOAP note, ICD-10 diagnosis, and allergy-aware prescription
   - **Longitudinal Patient EMR Synthesizer (`/api/ai/patient-summary`):** Embedded inside the **Patient 360° Profile** modal ("✨ Generate AI Summary") — synthesizes consultations, admissions, lab abnormalities, allergies, and dispensed medications
   - **Pharmacy Drug Interaction & Allergy Checker (`/api/ai/rx-check`):** Screens proposed prescriptions against the patient's recorded allergies and active hospital dispensings
   - **Executive Daily Briefing & Multi-Turn Q&A (`/api/ai/briefing`):** Stateful multi-turn advisor using `previous_interaction_id` over live hospital KPIs, bed occupancy, lab backlogs, pharmacy stock alerts, and revenue

### Enabling Live Gemini API (Optional)

Every Gemini feature works out-of-the-box using the built-in clinical engine, and automatically upgrades to live `gemini-3.8-flash` / `gemini-4-argon` calls when `GEMINI_API_KEY` is present in `~/.env`, the project `.env`, or entered in the **Gemini AI Hub** top bar:

```bash
pip install -U google-genai   # optional; server also supports direct zero-dep HTTPS REST to /v1beta/interactions
```

## Running Automated Tests

```bash
python3 tests/e2e.py
```
