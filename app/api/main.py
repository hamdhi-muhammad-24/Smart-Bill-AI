from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routers import billing, health, users
from app.auth.router import router as auth_router
from app.billing_scheduler import start_scheduler

from app.auth.dependencies import azure_scheme

def create_app() -> FastAPI:
    application = FastAPI(
        title="SLT Billing System",
        description="Core billing engine and API",
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router)
    application.include_router(billing.router)
    application.include_router(health.router)
    application.include_router(users.router)

    register_exception_handlers(application)
    
    @application.on_event("startup")
    async def startup_event():
        try:
            await azure_scheme.openid_config.load_config()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"Azure AD OpenID config load skipped: {e}")
        start_scheduler()
        
    return application

app = create_app()
