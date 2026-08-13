from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routers import billing, health, users, envelope
from app.auth.router import router as auth_router
from app.billing_scheduler import start_scheduler


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
        try:
            from sqlalchemy import text
            from app.db.base import SessionLocal
            with SessionLocal() as db:
                db.execute(text("ALTER TYPE gmf_upload_status ADD VALUE IF NOT EXISTS 'PARTIALLY_PROCESSED';"))
                db.commit()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").debug(f"Enum sync skipped or already exists: {e}")

        start_scheduler()
        try:
            from app.db.base import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TYPE gmf_upload_status ADD VALUE IF NOT EXISTS 'PARTIALLY_PROCESSED'"))
                conn.execute(text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMIN1'"))
                conn.execute(text("ALTER TYPE envelope_artwork_status_enum ADD VALUE IF NOT EXISTS 'DRAFT'"))
                conn.execute(text("ALTER TABLE gmf_uploads ADD COLUMN IF NOT EXISTS template_breakdown TEXT;"))
                conn.execute(text("ALTER TABLE envelope_artworks ADD COLUMN IF NOT EXISTS campaign_name TEXT;"))
                # New: multi-role access control tables
                conn.execute(text(
                    "DO $prs$ BEGIN "
                    "CREATE TYPE permission_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED'); "
                    "EXCEPTION WHEN duplicate_object THEN null; END $prs$;"
                ))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_role_grants (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role user_role NOT NULL,
                        granted_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_user_role_grant UNIQUE (user_id, role)
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS permission_requests (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        email TEXT NOT NULL,
                        requested_roles TEXT NOT NULL,
                        reason TEXT,
                        status permission_request_status NOT NULL DEFAULT 'PENDING',
                        reviewed_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
                        reviewed_at TIMESTAMPTZ,
                        rejection_note TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """))
                # Seed testuser016 as ADMIN if not present
                conn.execute(text(
                    "INSERT INTO users (email, role, is_active) "
                    "VALUES ('testuser016@intranet.slt.com.lk', 'ADMIN', true) "
                    "ON CONFLICT (email) DO UPDATE SET role = 'ADMIN', is_active = true;"
                ))
                # Grant all roles to testuser016
                conn.execute(text(
                    "WITH u AS (SELECT id FROM users WHERE email = 'testuser016@intranet.slt.com.lk') "
                    "INSERT INTO user_role_grants (user_id, role) "
                    "SELECT u.id, r.role FROM u, "
                    "(VALUES ('ADMIN'::user_role), ('GMF_HANDLER'::user_role), "
                    " ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role) "
                    "ON CONFLICT (user_id, role) DO NOTHING;"
                ))
                # Backfill existing non-CUSTOMER users
                conn.execute(text(
                    "INSERT INTO user_role_grants (user_id, role) "
                    "SELECT id, role FROM users WHERE role != 'CUSTOMER' "
                    "ON CONFLICT (user_id, role) DO NOTHING;"
                ))
                # Grant all portal roles to all ADMIN users
                conn.execute(text(
                    "WITH admins AS (SELECT id FROM users WHERE role = 'ADMIN') "
                    "INSERT INTO user_role_grants (user_id, role) "
                    "SELECT a.id, r.role FROM admins a, "
                    "(VALUES ('GMF_HANDLER'::user_role), ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role) "
                    "ON CONFLICT (user_id, role) DO NOTHING;"
                ))
                conn.commit()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"Database enum migration skipped: {e}")

        try:
            from app.billing.worker_queue import start_worker_threads
            start_worker_threads(4)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"Worker threads startup skipped: {e}")
        
    return application

app = create_app()
