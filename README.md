# SLT E-Bill System 🧾

> An automated, high-precision telecom billing and PDF generation system built for Sri Lanka Telecom (SLT). Ingests GMF (General Master File) billing data, computes exact financial charges, generates official PDF e-bills, and provides role-based Web Portals for administrators, operators, and customers.

---

## 🌟 Key Features

* **📥 GMF File Ingestion**: Real-time GMF file processing via Web UI drag-and-drop or monitored upload directory (`gmf_uploads`).
* **🎨 Dynamic Template Engine**: SmartAI template selection supporting multiple bill formats (`vat_home`, `nonvat_enterprise`, `summary_statement`, `vat_creditnote`, etc.).
* **💰 High-Precision Financial Math**: All monetary calculations use exact 2-decimal precision (`Decimal` type, `ROUND_HALF_UP`) to ensure zero rounding discrepancies.
* **📄 ReportLab PDF Generator**: Renders multi-page, production-ready SLT invoices with localized typography (Noto Sans Sinhala/Tamil), barcodes, and payment slips.
* **⚡ Multi-Threaded Async Worker Queue**: High-throughput batch billing processing with automated status tracking and retry resilience.
* **🔐 Role-Based Access Control**:
  * **Admin (`admin@slt.lk`)**: System-wide control, manual billing runs, metric dashboards, template previews.
  * **Billing Operator (`admin1@slt.lk`)**: Dedicated file upload hub and batch job status monitoring.
  * **Customer**: Account summary viewing and bill PDF downloads.
* **📅 Automated Scheduler**: APScheduler integration for automated monthly billing run execution.

---

## 🏗️ System Architecture & Workflow

```
                             ┌───────────────────────────────────┐
                             │       GMF File Ingestion          │
                             │  Web UI Upload / Monitored Directory
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │     Parsing & Template Engine     │
                             │   Models/SmartAI_Bill/templates    │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │     Core Calculation Engine       │
                             │  Exact Money Math (Decimal type)  │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│       PostgreSQL DB          │ │    ReportLab PDF Renderer    │ │  Output Directory Sync       │
│ Stores Accounts & Invoices   │ │   Generates SLT-style PDFs   │ │ Saved to ./output / Drive    │
└──────────────┬───────────────┘ └──────────────┬───────────────┘ └──────────────┬───────────────┘
               │                               │                               │
               └───────────────────────────────┼───────────────────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │      FastAPI & React Portals      │
                             │ Admin, Operator, Customer Access  │
                             └───────────────────────────────────┘
```

---

## 💻 Tech Stack

* **Backend Framework**: Python 3.11, FastAPI, Pydantic v2, Uvicorn
* **Database & ORM**: PostgreSQL 15, SQLAlchemy 2.0, Alembic Migrations
* **PDF Rendering**: ReportLab 4.x, PyPDF2, python-barcode, qrcode
* **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, TanStack Query
* **Task Management**: Async Worker Threads, APScheduler
* **Containerization**: Docker, Docker Compose

---

## 🛠️ Prerequisites

Before running the project locally, ensure you have the following installed:

* **Python**: 3.11 or higher
* **Node.js**: v18 or higher (with npm)
* **PostgreSQL**: 15 or higher (running service on `localhost:5432`)
* **Git**

---

## 🚀 Quick Start (Local Development)

### 1. Environment Setup

Clone the repository and copy the environment template:

```powershell
cp .env.example .env
```

Ensure your PostgreSQL credentials in `.env` match your local database instance:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=slt_ebill
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### 2. One-Command Startup (Windows / PowerShell)

To initialize the database, apply migrations, seed default admin users, and start all services in parallel, run:

```powershell
.\start.ps1 --setup
```

*(For subsequent launches after initial setup, simply run `.\start.ps1`)*

This script automatically launches three independent terminal windows:
1. **FastAPI Backend**: `http://localhost:8090`
2. **React Frontend**: `http://localhost:5173`
3. **Async Worker Queue**: Monitors and processes billing jobs in real time.

---

## 🔐 Default Access Credentials

| Role | Email | Password | Allowed Actions |
|---|---|---|---|
| **Admin** | `admin@slt.lk` | `admin123` | Full administrative control, billing runs, analytics |
| **Billing Operator** | `admin1@slt.lk` | `admin1123` | GMF uploads, queue status monitoring |

* **Frontend App**: [http://localhost:5173](http://localhost:5173)
* **Interactive API Documentation (Swagger)**: [http://localhost:8090/docs](http://localhost:8090/docs)

---

## 🐳 Production VM Deployment (Docker Compose)

For production deployment on a Linux VM (e.g., Ubuntu):

```bash
# 1. Pull latest code
git pull origin main

# 2. Build and start containers in background
docker compose -f docker-compose.prod.yml up --build -d

# 3. Apply database migrations
docker exec -it slt-billing-backend-1 alembic upgrade head

# 4. Seed initial admin users (if needed)
docker exec -it slt-billing-backend-1 python -m app.db.seed
```

---

## 🧪 Testing & Data Reset

### Run Automated Test Suite

To run the complete test suite verifying billing engine math, GMF parsers, and API endpoints:

```powershell
pytest -q
```

### Reset Test Data (Clean Slate)

To purge processed queue folders, clear output PDFs, and reset database tables during testing:

```powershell
python reset_test_data.py
```

---

## 📂 Project Directory Structure

```
SLT-Billing-System/
├── app/
│   ├── api/                 # FastAPI routes (billing, health, uploads, users)
│   ├── auth/                # JWT authentication & role-based middleware
│   ├── billing/             # Core calculation engine, repository & worker queue
│   ├── core/                # System configuration, money (Decimal) & logging
│   ├── db/                  # SQLAlchemy models, sessions & database seeders
│   ├── pdf/                 # ReportLab PDF layout & asset managers
│   └── uploads/             # GMF filesystem watcher service
├── frontend/                # React + TypeScript + Vite Web Application
│   └── src/
│       ├── components/      # Reusable UI components & layouts
│       └── pages/admin/     # Admin & Operator portals (Uploads, Monitor, Preview)
├── Models/SmartAI_Bill/     # Invoice template registry & template-specific parsers
├── migrations/              # Alembic database version migration scripts
├── output/                  # Storage directory for generated PDF invoices
├── start.ps1                # One-command local startup script
├── reset_test_data.py       # Data wipe script for testing environments
├── docker-compose.prod.yml  # Production Docker Compose orchestration
└── pyproject.toml           # Python package & dependency specifications
```

---

## 📐 Core Engineering Principles

1. **Strict Money Decimal Types**: Money is represented strictly using Python `Decimal` / DB `NUMERIC(12,2)`. Floating-point numbers are strictly forbidden to eliminate rounding errors.
2. **Immutable Snapshot Invoices**: Once an invoice is generated and saved, calculated values are frozen. Invoices are never recalculated dynamically on read.
3. **Framework Independence**: The core billing and PDF rendering engine operate independently of the Web/API layer, ensuring isolated testability.
4. **Idempotent Batch Runs**: Batch jobs skip already processed accounts for a period and gracefully log errors without halting the entire run.
