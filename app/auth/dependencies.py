from typing import Any
from fastapi import Depends, HTTPException, Header, Query, Request, status
from sqlalchemy.orm import Session
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from fastapi_azure_auth.user import User as AzureUser

from app.api.deps import get_db
from app.auth import repository as auth_repo
from app.auth.pdf_tokens import verify_pdf_token
from app.auth.schemas import UserOut
from app.core.config import settings

azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=settings.azure_client_id or "default-client-id",
    tenant_id=settings.azure_tenant_id or "default-tenant-id",
    scopes={
        f"api://{settings.azure_client_id}/user_impersonation": "User impersonation"
    } if settings.azure_client_id else {},
)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    authorization = request.headers.get("authorization", "")

    # 1. Dev test token bypass for local development & testing
    if authorization and "Bearer dev-" in authorization:
        token = authorization.split("Bearer dev-")[-1].strip().lower()
        target_email = "admin@slt.lk"
        if "gmf" in token:
            target_email = "gmf@slt.lk"
        elif "manager" in token:
            target_email = "manager@slt.lk"
        
        user = auth_repo.get_user_by_email(db, target_email)
        if user and user.is_active:
            return UserOut(id=user.id, email=user.email, role=user.role.value)

    # 2. Azure scheme validation
    try:
        azure_user = await azure_scheme(request)
    except Exception:
        # Fallback for local testing if client_id is dummy or absent
        if not settings.azure_client_id or settings.azure_client_id == "default-client-id":
            user = auth_repo.get_user_by_email(db, "admin@slt.lk")
            if user:
                return UserOut(id=user.id, email=user.email, role=user.role.value)
        raise _401

    email = getattr(azure_user, "preferred_username", None) or getattr(azure_user, "email", None)
    if isinstance(azure_user, dict):
        email = azure_user.get("preferred_username") or azure_user.get("email")

    if not email:
        raise _401

    user = auth_repo.get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise _401

    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
    )

def require_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_manager(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    if current_user.role != "MANAGER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return current_user


def require_gmf_handler_or_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    if current_user.role not in ("ADMIN", "GMF_HANDLER", "ADMIN1"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or GMF Handler access required",
        )
    return current_user

# Alias for backward compatibility
require_admin1_or_admin = require_gmf_handler_or_admin
