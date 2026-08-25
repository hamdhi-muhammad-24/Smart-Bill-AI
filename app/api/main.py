from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routers import billing, health, users, envelope
from app.auth.router import router as auth_router
from app.billing_scheduler import start_scheduler
import logging

# Suppress noisy warnings from fastapi_azure_auth when it fails to validate a Graph API token
logging.getLogger("fastapi_azure_auth").setLevel(logging.ERROR)
# Suppress noisy uvicorn access logs (200 OK) from constant frontend polling
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def create_app() -> FastAPI:
    application = FastAPI(
        title="SLT Billing System",
        description="Core billing engine and API",
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8090", "http://127.0.0.1:8090", "*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router)
    application.include_router(billing.router)
    application.include_router(health.router)
    application.include_router(users.router)
    application.include_router(envelope.router)

    register_exception_handlers(application)
    
    @application.on_event("startup")
    async def startup_event():
        start_scheduler()
        try:
            from app.db.base import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                # 1. Enums
                for stmt in [
                    "ALTER TYPE gmf_upload_status ADD VALUE IF NOT EXISTS 'PARTIALLY_PROCESSED';",
                    "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMIN1';",
                    "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'GMF_HANDLER';",
                    "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ENVELOPE_HANDLER';",
                    "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'MANAGER';",
                    "ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'CUSTOMER';",
                    "DO $enum$ BEGIN CREATE TYPE envelope_type_enum AS ENUM ('LARGE', 'MEDIUM', 'SELF_SEAL'); EXCEPTION WHEN duplicate_object THEN null; END $enum$;",
                    "DO $enum$ BEGIN CREATE TYPE envelope_artwork_status_enum AS ENUM ('ACTIVE', 'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'REPLACED', 'REMOVED'); EXCEPTION WHEN duplicate_object THEN null; END $enum$;",
                    "ALTER TYPE envelope_artwork_status_enum ADD VALUE IF NOT EXISTS 'DRAFT';",
                    "DO $prs$ BEGIN CREATE TYPE permission_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED'); EXCEPTION WHEN duplicate_object THEN null; END $prs$;",
                ]:
                    try:
                        conn.execute(text(stmt))
                        conn.commit()
                    except Exception as e:
                        logging.getLogger("uvicorn").debug(f"Enum sync stmt skipped: {e}")

                # 2. Tables & Columns
                for stmt in [
                    "ALTER TABLE gmf_uploads ADD COLUMN IF NOT EXISTS template_breakdown TEXT;",
                    """CREATE TABLE IF NOT EXISTS envelope_templates (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        envelope_type envelope_type_enum NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        base_pdf_path TEXT NOT NULL,
                        box_x0 DOUBLE PRECISION,
                        box_y0 DOUBLE PRECISION,
                        box_x1 DOUBLE PRECISION,
                        box_y1 DOUBLE PRECISION,
                        rotation_deg INTEGER NOT NULL DEFAULT 0,
                        fit_mode TEXT NOT NULL DEFAULT 'cover',
                        min_width INTEGER NOT NULL DEFAULT 800,
                        min_height INTEGER NOT NULL DEFAULT 250,
                        aspect_min INTEGER NOT NULL DEFAULT 70,
                        aspect_max INTEGER NOT NULL DEFAULT 350,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );""",
                    """CREATE TABLE IF NOT EXISTS envelope_artworks (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        envelope_template_id BIGINT NOT NULL REFERENCES envelope_templates(id) ON DELETE CASCADE,
                        original_filename TEXT NOT NULL,
                        campaign_name TEXT,
                        image_path TEXT NOT NULL,
                        image_width INTEGER NOT NULL,
                        image_height INTEGER NOT NULL,
                        output_pdf_path TEXT,
                        preview_png_path TEXT,
                        status envelope_artwork_status_enum NOT NULL DEFAULT 'ACTIVE',
                        rejection_reason TEXT,
                        uploaded_by TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        replaced_at TIMESTAMPTZ
                    );""",
                    "ALTER TABLE envelope_artworks ADD COLUMN IF NOT EXISTS campaign_name TEXT;",
                    """CREATE TABLE IF NOT EXISTS envelope_history (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        template_name TEXT NOT NULL,
                        action TEXT NOT NULL,
                        filename TEXT,
                        reason TEXT,
                        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );""",
                    """CREATE TABLE IF NOT EXISTS user_role_grants (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role user_role NOT NULL,
                        granted_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_user_role_grant UNIQUE (user_id, role)
                    );""",
                    """CREATE TABLE IF NOT EXISTS permission_requests (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        email TEXT NOT NULL,
                        requested_roles TEXT NOT NULL,
                        reason TEXT,
                        status permission_request_status NOT NULL DEFAULT 'PENDING',
                        reviewed_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        reviewed_at TIMESTAMPTZ,
                        rejection_note TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );""",
                    """INSERT INTO users (email, role, is_active)
                    VALUES ('testuser016@intranet.slt.com.lk', 'ADMIN', true)
                    ON CONFLICT (email) DO UPDATE SET role = 'ADMIN', is_active = true;""",
                    """WITH u AS (SELECT id FROM users WHERE email = 'testuser016@intranet.slt.com.lk')
                    INSERT INTO user_role_grants (user_id, role)
                    SELECT u.id, r.role FROM u,
                    (VALUES ('ADMIN'::user_role), ('GMF_HANDLER'::user_role),
                     ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role)
                    ON CONFLICT (user_id, role) DO NOTHING;""",
                    """INSERT INTO user_role_grants (user_id, role)
                    SELECT id, role FROM users WHERE role != 'CUSTOMER'
                    ON CONFLICT (user_id, role) DO NOTHING;""",
                    """WITH admins AS (SELECT id FROM users WHERE role = 'ADMIN')
                    INSERT INTO user_role_grants (user_id, role)
                    SELECT a.id, r.role FROM admins a,
                    (VALUES ('GMF_HANDLER'::user_role), ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role)
                    ON CONFLICT (user_id, role) DO NOTHING;""",
                ]:
                    try:
                        conn.execute(text(stmt))
                        conn.commit()
                    except Exception as e:
                        logging.getLogger("uvicorn").debug(f"DDL/Seed stmt skipped: {e}")

            # Auto-seed envelope templates
            from app.api.routers.envelope import _ensure_envelope_templates_seeded
            from app.db.base import SessionLocal
            with SessionLocal() as db:
                _ensure_envelope_templates_seeded(db)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"Database schema initialization: {e}")

        import os
        if os.environ.get("RUN_IN_PROCESS_WORKER", "true").lower() == "true":
            try:
                from app.billing.worker_queue import start_worker_threads
                start_worker_threads(4)
            except Exception as e:
                import logging
                logging.getLogger("uvicorn").warning(f"Worker threads startup skipped: {e}")
        
    return application

app = create_app()
