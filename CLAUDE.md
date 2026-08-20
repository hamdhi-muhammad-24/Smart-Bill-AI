# CLAUDE.md — SLT E-Bill System
# ============================================================
# READ THIS FILE FIRST BEFORE MAKING ANY CHANGES
# This file is the single source of truth for the current
# state of the project. Always read it before starting any task.
# ============================================================

## System Overview

The **SLT E-Bill System** is an enterprise-grade billing, demand notice, and envelope composition platform built for Sri Lanka Telecom (SLT). It ingests billing data files (GMF text formats, Excel `.xlsx`/`.xls`, CSV), identifies the appropriate invoice/notice template, renders pixel-perfect PDF bills and notices in bulk, and composes marketing artwork onto postal envelopes.

The system is deployed on a production Linux VM and also supports full local Windows development.

---

## Architecture Overview

```
frontend/                 React 18 + Vite + Tailwind CSS + Lucide Icons + Shadcn UI
  src/
    auth/                 Microsoft MSAL config & AuthProvider (Azure AD + Graph API)
    components/           AdminLayout, Admin1Layout, EnvelopeLayout, ManagerLayout, UI kit
    lib/                  api.ts (REST client), uploadQueue.ts, utils
    pages/
      Login.tsx           Single Sign-On (Microsoft Entra ID) + Dev quick logins
      RoleSelector.tsx    Portal selector for users holding multiple roles
      RequestAccess.tsx   Self-service role permission request workflow
      PublicPortal.tsx    Public facing landing page
      admin/              System Admin Console (Dashboard, Monitor, Preview, Generation, Archive, Templates, Logs)
      envelope/           Envelope Operations Portal (Dashboard, Manager Workspace, Saved Artwork Gallery)
app/
  api/
    main.py               FastAPI application factory, CORS, auto-migrations, scheduler init
    routers/
      billing.py          Billing runs, GMF uploads, template approvals, stats, output archive
      envelope.py         Envelope templates, artwork upload, PyMuPDF composite PDF generation
      users.py            User role grants, access requests, user management API
      health.py           Health check endpoint
  auth/                   Azure AD JWT validation + MS Graph fallback + Dev token auth
  billing/                Worker queue, scheduler, batch management, and GMF core pipeline
    worker_queue.py       Async background queue with atomic DB increments & file-lock retries
    gmf_core/             GMF parser, splitter, template identifier, QR/barcode generators
  core/                   Settings (Pydantic), logging, money arithmetic
  db/                     SQLAlchemy models (PostgreSQL), Base, SessionLocal, synthetic seed
  uploads/                watcher.py (Watchdog filesystem watcher for incoming GMFs)
  scheduler/              Celery + Redis scheduled billing tasks
migrations/               Alembic migration version scripts
Models/SmartAI_Bill/      Core billing, demand letter, and envelope rendering engine
  core/                   GMF reader, splitter, template identifier
  processing/             Batch processor, PDF compressor, output manager
  templates/              15 template implementations + Envelope composition
docker-compose.prod.yml   Production multi-container Docker Compose setup
docker-compose.yml        Local dev support services (Redis, Mailpit)
start.ps1                 One-command local development startup script
```

---

## Role-Based Portals & Access Control

The platform uses a role-based access model with multi-role grants (`user_role_grants`) and self-service permission requests (`permission_requests`).

| Role | Portal Route | Primary Capabilities |
|---|---|---|
| **ADMIN** | `/admin` | Full system control: billing runs, approvals, template toggles, output archive, activity logs |
| **GMF_HANDLER** *(ADMIN1)* | `/gmf-handler` | Operations portal: GMF file uploads, format validation, pipeline monitoring |
| **ENVELOPE_HANDLER** | `/envelope-handler` | Envelope workspace: artwork placement, coordinate mapping, composite generation, gallery |
| **MANAGER** | `/manager` | User administration: review access requests, assign/revoke portal role grants |
| **CUSTOMER** | `/` | Public view / awaiting access assignment |

### Authentication Modes:
1. **Microsoft Entra ID (Azure AD / MSAL):** Enterprise Single Sign-On using Microsoft corporate credentials (`User.Read` scope + Graph API fallback).
2. **Superuser Account:** `testuser016@intranet.slt.com.lk` (always receives full cross-portal access).
3. **Local Dev Tokens:** Fast switching via `Bearer dev-admin`, `Bearer dev-gmf`, `Bearer dev-manager`, `Bearer dev-envelope`.

---

## Template Registry (15 Core Bill & Notice Templates)

All templates are registered in `Models/SmartAI_Bill/templates/registry.py`:

| Template ID | Name / Description | Classification / Billstyle |
|---|---|---|
| `nonvat_home` | Non-VAT Home Invoice | Sheet 19 — Non-VAT, Home |
| `nonvat_enterprise` | Non-VAT Enterprise Invoice | Sheet 19 — Non-VAT, Enterprise |
| `vat_home` | VAT Home Invoice | Sheet 18 — BILLSTYLE=1, BILLTYPE=1, Home |
| `vat_enterprise` | VAT Enterprise Invoice | Sheet 18 — BILLSTYLE=1, BILLTYPE=1, Enterprise |
| `lod` | Letter of Demand & Termination | Certified Sinhala/Tamil Translation Notice |
| `vat_confirmation` | VAT Number Confirmation | VAT Registration Verification Letter |
| `final_notice` | Final Notice Demand Letter | LTE Final Notice (supports Excel/CSV) |
| `customer_letter_logo_v1print` | Customer Migration Letter | Logo V1 Print Notice (Excel/CSV) |
| `product_label_grouping` | Product Label Level Grouping | Sheet 22 — BILLSTYLE=19 |
| `subscription_ref_grouping` | Subscription Ref Level Grouping | Sheet 23 — BILLSTYLE=20 |
| `summary_statement` | Summary Statement | Sheet 7 — DOCTYPE=SUMMARYSTATEMENT |
| `invoice_of_summary` | Invoice of Summary | BILLSTYLE=18 |
| `vat_creditnote` | VAT Credit Note | BILLSTYLE=6 |
| `nonvat_creditnote` | Non-VAT Credit Note | BILLSTYLE=16 |
| `usd_open_item` | USD Open Item | BILLSTYLE=21 (Foreign currency) |

### Envelope Templates (PyMuPDF Compositor):
- **SLT Large Envelope** (`05717-SLT Large Envelope.pdf` — 1350x1139 pt, aspect 0.70–1.40)
- **SLT Medium Envelope** (`05717-SLT Medium Envelope.pdf` — 763x981 pt, aspect 1.50–2.50)
- **SLT Self-Seal A4 Envelope** (`05717-SLT Self Seal-01.pdf` — 589x842 pt, aspect 2.50–4.50)

---

## Deployments & Environments

### 1. Local Development (Windows)
- **Start command:** `.\start.ps1` (or `.\start.ps1 --setup` to run migrations + seed)
- **Frontend:** `http://localhost:5173`
- **Backend API:** `http://localhost:8090` (Docs: `http://localhost:8090/docs`)
- **Database:** PostgreSQL on `localhost:5432` (`slt_ebill`)
- **Worker Queue:** Runs via `app.billing.worker_queue`
- **GMF Uploads Directory:** `./local_gmf_uploads` (or Google Drive mount)
- **Output PDFs:** `./output`

### 2. Production VM (SLM-EKB)
- **Host IP:** `206.189.159.175`
- **SSH:** `ssh root@206.189.159.175`
- **Project path on VM:** `/root/slt-billing`
- **Frontend:** `http://206.189.159.175:8080`
- **Backend API:** `http://206.189.159.175:8000`
- **GMF Uploads Path:** `/var/slt-billing/gmf_uploads` -> `/app/gmf_uploads`
- **Output Invoices Path:** `/var/slt-billing/output_invoices` -> `/app/output`
- **Google Drive Sync:** `rclone` syncs `/var/slt-billing/output_invoices` -> `gdrive:SLT_Output_Invoices` every 5 min via cron.
- **Docker Compose:** `docker-compose.prod.yml`
- **Protected other services on VM (DO NOT TOUCH):** `langfuse` (port 3000), `ai_agents` (ports 8100/3100)

---

## Important Development Conventions

1. **Exact Money Arithmetic:** Always use `Decimal` with 2 decimal places and `ROUND_HALF_UP`. Never use IEEE `float` for monetary calculations.
2. **Framework-Independent Billing Engine:** `Models/SmartAI_Bill/` contains pure parsing and rendering logic without FastAPI or web dependencies.
3. **Thin API Layer:** Routers in `app/api/routers/` handle validation, database transactions, and call engine services; do not put raw billing math or rendering code in routers.
4. **Idempotent Batch Runs & Atomic Increments:** Use atomic SQL increments (`processed_records_count`) and robust file operation retries (`_robust_file_op`) to avoid Windows/Linux file locking issues.
5. **Preserve System Stability:** Never alter running production workflows, background worker queues, or template registry schemas without verifying backwards compatibility.
6. **No PII in Git:** Test files and seed data must use synthetic mock data.

---

## VM Deployment Commands

```bash
# 1. Commit and push from local
git add .
git commit -m "your message"
git push origin <branch>

# 2. On VM SSH terminal:
cd /root/slt-billing
git pull origin <branch>
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up --build -d

# 3. Database migrations / Seeding on VM (if needed)
docker exec -it slt-billing-backend-1 alembic upgrade head
docker exec -it slt-billing-backend-1 python -m app.db.seed

# 4. Clean reset of test data on VM (if requested)
docker exec -it slt-billing-backend-1 python reset_test_data.py -y
rclone sync /var/slt-billing/output_invoices gdrive:SLT_Output_Invoices
```