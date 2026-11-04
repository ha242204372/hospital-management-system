# MediCare HMS — Clinical & Finance Workflow

## End-to-end patient journey

1. **Front Desk**
   - Register patient → `Patients`
   - Book appointment → `Appointments`

2. **Clinical**
   - Consultation (OPD) → `Consultations (EMR)`
   - Admit if needed → `Admissions (IPD)` + assign bed
   - Discharge → action on admission (releases bed)

3. **Diagnostics**
   - Order lab → `Lab Orders`
   - Complete result → update status to Completed

4. **Pharmacy**
   - Dispense → `Dispensing` (reduces stock)
   - Restock via inventory action

5. **Finance**
   - Charges land on invoice → `Billing & Invoices`
   - Record payment
   - Track expenses & assets → `Expenses`, `Assets`
   - Overview → `Accounts & Finance` hub + Dashboard KPIs

## Role map

| Role | Primary work |
|------|----------------|
| Admin | Setup, users, all modules |
| Receptionist | Patients, appointments, invoices |
| Doctor | EMR, admissions, lab orders |
| Nurse | Admissions, beds, labs, dispensing view |
| Lab Technician | Lab orders & catalog |
| Pharmacist | Inventory & dispensing |
| Accountant | Invoices, expenses, assets, reports |
| Patient | Own records only |

## Integrity rules

- Admissions require available bed; discharge frees it
- Dispensing checks stock and reduces it
- Invoice total = sum of items; paid = sum of payments
- Expenses/Assets tables created on first finance access
- Audit log records key actions (quoted `"user"` on PostgreSQL)

## Database

- Default: SQLite `database/hospital.db`
- PostgreSQL: set `DATABASE_URL=postgresql://user:pass@host:5432/hospital`
- Migrate: `python3 migrate_to_postgres.py`
