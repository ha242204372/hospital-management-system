# VizMedCare — Current features

Date: 2026-11-05. Based on the running local app and code.

## Working today
| Module | What exists |
|--------|-------------|
| Staff portal login | Role cards (Reception, Doctor, Pharmacy, Lab, Accounts, Nursing, Admin, Patient) with demo fill |
| Patients | Register, search, profile |
| Appointments | Book, complete, cancel. English month dropdowns |
| OPD queue | Today’s scheduled list + upcoming |
| EMR | Consultations, notes, diagnosis, print |
| Prescriptions | Linked to encounters |
| MAR | Medication admin records |
| IPD | Admissions, wards, beds, discharge summary |
| Lab | Test catalog, orders |
| Pharmacy | Medicines, stock, expiry flag, dispensing |
| Billing | Invoices, items, payments (Cash, Card, Bank, JazzCash, EasyPaisa, Raast, Insurance), thermal receipt, WhatsApp share |
| Finance | KPIs, P&L, balance sheet, GL summary |
| Expenses & assets | Tables present |
| AI | Gemini triage, copilot, Rx check, inventory forecast (needs API key) |
| Roles | 7 roles; Doctor menu is clinical-only |
| Themes | Multiple skins, white-label name/currency |
| DB | SQLite default, PostgreSQL optional |

## Gaps vs a Pakistan clinic (from this audit)
- No Urdu / RTL
- No numbered queue token or TV display
- Thermal print is CSS only, not ESC/POS 58/80 mm
- No CNIC field, no +92 phone validation
- No doctor fee split, no panel / Sehat Card claims
- No batch/FEFO pharmacy, no purchase orders
- No FBR invoice number / QR
- No WhatsApp bot or SMS (only a share link)
- No patient self-service portal
- No multi-branch, HR, or payroll
- No CSV import wizard or one-click restore
