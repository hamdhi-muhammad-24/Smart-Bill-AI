import asyncio
import json
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, HTTPException, Request, status
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from sqlalchemy.orm import Session
from fastapi.security import SecurityScopes

from app.api.deps import get_db
from app.auth import repository as auth_repo
from app.auth.schemas import UserOut
from app.core.config import settings
from app.db.models import UserRoleGrant

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


def _get_granted_roles(db: Session, user_id: int) -> List[str]:
    """Return all role names granted to the given user."""
    grants = db.query(UserRoleGrant).filter(UserRoleGrant.user_id == user_id).all()
    return [g.role.value for g in grants]


# The one account that always retains full cross-portal access regardless of grants.
_SUPERUSER_EMAIL = "testuser016@intranet.slt.com.lk"
_ALL_PORTAL_ROLES = {"ADMIN", "GMF_HANDLER", "ENVELOPE_HANDLER", "MANAGER"}


def _build_user_out(db: Session, user) -> UserOut:
    """Build a fully-populated UserOut from a DB user row."""
    roles = _get_granted_roles(db, user.id)
    primary = user.role.value if hasattr(user.role, "value") else str(user.role)
    # testuser016 always has every portal role regardless of DB grants
    if user.email == _SUPERUSER_EMAIL:
        all_roles = list(_ALL_PORTAL_ROLES | set(roles))
    else:
        all_roles = roles if roles else [primary]
    return UserOut(
        id=user.id,
        email=user.email,
        role=primary,
        roles=all_roles,
        is_new_user=False,
    )


def _fetch_graph_email(access_token: str) -> str | None:
    """Validate a User.Read token through Graph and return the signed-in email."""
    graph_request = UrlRequest(
        "https://graph.microsoft.com/v1.0/me?$select=userPrincipalName,mail",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urlopen(graph_request, timeout=10) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None
    return profile.get("userPrincipalName") or profile.get("mail")


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    authorization = request.headers.get("authorization", "")

    # 1. Dev test token bypass for local development & testing
    if authorization.startswith("Bearer dev-"):
        token = authorization.removeprefix("Bearer dev-").strip().lower()
        target_email = "admin@slt.lk"
        if "gmf" in token:
            target_email = "gmf@slt.lk"
        elif "manager" in token:
            target_email = "manager@slt.lk"
        elif "envelope" in token:
            target_email = "envelope@slt.lk"

        user = auth_repo.get_user_by_email(db, target_email)
        if user is not None and getattr(user, "is_active", False):
            return _build_user_out(db, user)
        raise _401

    # 2. Validate an API token and extract the user's email.
    try:
        azure_user = await azure_scheme(request, SecurityScopes(scopes=[]))
        email = getattr(azure_user, "preferred_username", None) or getattr(azure_user, "email", None)
        if isinstance(azure_user, dict):
            email = azure_user.get("preferred_username") or azure_user.get("email")
    except Exception:
        # User.Read tokens target Microsoft Graph rather than this API.
        raw_token = authorization.removeprefix("Bearer ").strip()
        email = await asyncio.to_thread(_fetch_graph_email, raw_token)

    if not email:
        raise _401

    user = auth_repo.get_user_by_email(db, email)

    # New user — not in DB yet; return a minimal UserOut flagged as new
    if user is None:
        return UserOut(
            id=0,
            email=email,
            role="CUSTOMER",
            roles=[],
            is_new_user=True,
        )

    if not getattr(user, "is_active", False):
        raise _401

    return _build_user_out(db, user)


# ── Role guards ──────────────────────────────────────────────────────────────

def require_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    if "ADMIN" not in current_user.roles and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_manager(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    allowed = {"MANAGER"}
    if not (allowed & set(current_user.roles)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return current_user


def require_gmf_handler_or_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    allowed = {"GMF_HANDLER", "ADMIN1"}
    if not (allowed & set(current_user.roles)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GMF Handler access required",
        )
    return current_user


def require_envelope_handler_or_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    allowed = {"ENVELOPE_HANDLER"}
    if not (allowed & set(current_user.roles)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Envelope Handler access required",
        )
    return current_user


# Alias for backward compatibility
require_admin1_or_admin = require_gmf_handler_or_admin
