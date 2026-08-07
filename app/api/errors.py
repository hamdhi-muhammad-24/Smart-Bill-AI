"""
API-layer exception classes and FastAPI exception handlers.

Domain errors the engine/repository already raise (ValueError) are mapped here
to HTTP status codes so no error-handling logic lives in routers.

Handler registration order matters — register specific types before generic ones.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Error response schema (for OpenAPI docs)
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# API-layer domain exception classes
# (defined here, in the API layer — the engine never imports these)
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised by routers when a requested resource does not exist."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class DuplicateInvoice(Exception):
    """Raised when generate-one is called for an account+period that already
    has a GENERATED (frozen) invoice."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def not_found_handler(request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


async def duplicate_invoice_handler(
    request: Request, exc: DuplicateInvoice
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.detail})


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # The billing repository raises ValueError for every "not found" condition
    # (unknown account, missing invoice for a period). Map them all to 404.
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    import traceback
    print(f"\n[UNHANDLED EXCEPTION] {request.method} {request.url.path}: {exc}")
    traceback.print_exc()
    log.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server error: {str(exc)}"},
    )


# ---------------------------------------------------------------------------
# Convenience helper — called once from create_app()
# ---------------------------------------------------------------------------

def register_exception_handlers(app) -> None:  # type: ignore[type-arg]
    """Attach all exception handlers to the FastAPI application."""
    app.add_exception_handler(NotFound,           not_found_handler)
    app.add_exception_handler(DuplicateInvoice,   duplicate_invoice_handler)
    app.add_exception_handler(ValueError,         value_error_handler)
    # Generic handler last — only fires for exceptions not caught above.
    # FastAPI's built-in HTTPException and RequestValidationError handlers
    # take precedence (Starlette matches the most-specific type first).
    app.add_exception_handler(Exception,          unhandled_exception_handler)
