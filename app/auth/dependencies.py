import asyncio
import base64
import hashlib
import json
import logging
import time
import threading
from typing import List, Optional
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

logger = logging.getLogger(__name__)

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

# ── Ultra-Fast In-Memory Auth Caches ──────────────────────────────────────────
_CACHE_LOCK = threading.Lock()
# Maps token_sha256 -> (email, expires_at_timestamp)
_TOKEN_EMAIL_CACHE: dict[str, tuple[str, float]] = {}
# Maps email -> (UserOut, expires_at_timestamp)
_USER_OUT_CACHE: dict[str, tuple[UserOut, float]] = {}

TOKEN_CACHE_TTL = 900.0   # 15 minutes token email cache
USER_CACHE_TTL = 60.0     # 60 seconds user role cache


def invalidate_user_cache(email: Optional[str] = None) -> None:
    """Invalidates the cached UserOut data so role/permission updates take effect immediately."""
    with _CACHE_LOCK:
        if email:
            _USER_OUT_CACHE.pop(email.strip().lower(), None)
        else:
            _USER_OUT_CACHE.clear()


def _extract_email_from_jwt(token: str) -> Optional[str]:
    """
    Instantly decodes standard JWT payload to extract user email/username
    without any external network requests (0.001 ms).
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)

        # Standard Microsoft Entra ID claims
        email = (
            payload.get("preferred_username")
            or payload.get("email")
            or payload.get("upn")
            or payload.get("unique_name")
        )
        if email and isinstance(email, str) and "@" in email:
            return email.strip().lower()

        # Alternate array claim
        emails = payload.get("emails")
        if isinstance(emails, list) and emails and isinstance(emails[0], str) and "@" in emails[0]:
            return emails[0].strip().lower()

        return None
    except Exception:
        return None


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


def _fetch_graph_email(access_token: str) -> Optional[str]:
    """Validate a User.Read token through Graph and return the signed-in email."""
    graph_request = UrlRequest(
        "https://graph.microsoft.com/v1.0/me?$select=userPrincipalName,mail",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urlopen(graph_request, timeout=5) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None
    email = profile.get("userPrincipalName") or profile.get("mail")
    return email.strip().lower() if email else None


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

    raw_token = authorization.removeprefix("Bearer ").strip()
    if not raw_token:
        raise _401

    now = time.time()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # 2. Check token email cache
    email: Optional[str] = None
    with _CACHE_LOCK:
        cached_entry = _TOKEN_EMAIL_CACHE.get(token_hash)
        if cached_entry and cached_entry[1] > now:
            email = cached_entry[0]

    # 3. If not cached, extract locally from JWT first (instant 0ms)
    if not email:
        email = _extract_email_from_jwt(raw_token)

        # 4. If still not found, try azure_scheme or Microsoft Graph fallback
        if not email:
            try:
                azure_user = await azure_scheme(request, SecurityScopes(scopes=[]))
                email = getattr(azure_user, "preferred_username", None) or getattr(azure_user, "email", None)
                if isinstance(azure_user, dict):
                    email = azure_user.get("preferred_username") or azure_user.get("email")
            except Exception:
                email = await asyncio.to_thread(_fetch_graph_email, raw_token)

        if not email:
            raise _401

        email = email.strip().lower()
        with _CACHE_LOCK:
            _TOKEN_EMAIL_CACHE[token_hash] = (email, now + TOKEN_CACHE_TTL)

    # 5. Check UserOut object cache (avoids DB query for every single request)
    with _CACHE_LOCK:
        cached_user = _USER_OUT_CACHE.get(email)
        if cached_user and cached_user[1] > now:
            return cached_user[0]

    # 6. Database lookup
    user = auth_repo.get_user_by_email(db, email)

    # New user — not in DB yet; return a minimal UserOut flagged as new
    if user is None:
        user_out = UserOut(
            id=0,
            email=email,
            role="CUSTOMER",
            roles=[],
            is_new_user=True,
        )
        with _CACHE_LOCK:
            _USER_OUT_CACHE[email] = (user_out, now + USER_CACHE_TTL)
        return user_out

    if not getattr(user, "is_active", False):
        raise _401

    user_out = _build_user_out(db, user)
    with _CACHE_LOCK:
        _USER_OUT_CACHE[email] = (user_out, now + USER_CACHE_TTL)

    return user_out


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
