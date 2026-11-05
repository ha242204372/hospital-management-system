# VizMedCare — Architecture

Date: 2026-11-05

## Stack
- Python HTTP server (`server.py`), no Flask
- Single-page frontend: `static/index.html` + `static/app.js` + `static/style.css`
- SQLite by default (`database/hospital.db`), optional PostgreSQL via `DATABASE_URL`
- Compatibility layer in `app/models/db.py` (`USE_POSTGRES`, `?` → `%s`)

## Layout
| Path | Role |
|------|------|
| `server.py` | Routes, static serving, API dispatch |
| `app/models/db.py` | Connect, query helpers, settings, audit |
| `app/models/schema_registry.py` | Resources, fields, roles, SQL |
| `app/models/seed.py` | Schema + demo seed |
| `app/controllers/` | auth, crud, analytics, accounts, ai, db, settings |
| `static/` | SPA (login portal, dashboard, tables) |
| `gemini_ai.py` | Gemini clinical features |

## Roles
Admin, Doctor, Nurse, Receptionist, Pharmacist, Lab Technician, Accountant, Patient

## Main routes
| Route | Purpose |
|-------|---------|
| `/api/login` `/api/logout` `/api/meta` | Auth and menu |
| `/api/r/<resource>` | CRUD lists |
| `/api/dashboard` `/api/reports` | Analytics |
| `/api/queue/today` | OPD queue |
| `/api/accounts/*` | Finance KPIs, P&L, GL |
| `/api/ai/*` | Gemini triage, copilot, Rx check |
| `/api/settings` | White-label hospital setup |

## How the SPA calls the API
`api(path)` in `static/app.js` fetches `/api` + path with JSON. Navigation is hash-based (`#dashboard`, `#opd_queue`, `#medicines`). Role filters the sidebar and the resource list from `/api/meta`.

## Database
Core tables: patients, appointments, encounters, admissions, wards, beds, lab_tests, lab_orders, medicines, dispensing, invoices, invoice_items, payments, expenses, assets, staff, users, audit_log, settings, prescriptions, mar (extra tables created at boot).
