import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_current_user
from app.auth.schemas import UserOut
from app.db.models import (
    PermissionRequest,
    PermissionRequestStatus,
    User,
    UserRole,
    UserRoleGrant,
)

router = APIRouter(prefix="/users", tags=["user-management"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    role: str  # primary role: ADMIN, GMF_HANDLER, MANAGER, ENVELOPE_HANDLER
    roles: List[str] = []   # optional extra roles to grant simultaneously
    is_active: bool = True


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    roles: List[str] = []
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AccessRequestPayload(BaseModel):
    email: str                      # from Microsoft account
    requested_roles: List[str]      # e.g. ["GMF_HANDLER", "MANAGER"]
    reason: Optional[str] = None


class PermissionRequestResponse(BaseModel):
    id: int
    email: str
    requested_roles: List[str]
    reason: Optional[str]
    status: str
    reviewed_at: Optional[str]
    rejection_note: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class RoleUpdatePayload(BaseModel):
    roles: List[str]  # full set of roles to grant


class RejectRequestPayload(BaseModel):
    note: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_manager(current_user: UserOut):
    allowed = {"MANAGER"}
    if not (allowed & set(current_user.roles)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )


def _get_grants(db: Session, user_id: int) -> List[str]:
    grants = db.query(UserRoleGrant).filter(UserRoleGrant.user_id == user_id).all()
    return [g.role.value for g in grants]


def _to_user_response(db: Session, u: User) -> UserResponse:
    roles = _get_grants(db, u.id)
    primary = u.role.value if hasattr(u.role, "value") else str(u.role)
    return UserResponse(
        id=u.id,
        email=u.email,
        role=primary,
        roles=roles,
        is_active=u.is_active,
        created_at=u.created_at.isoformat() if u.created_at else None,
    )


# ── Existing user endpoints ──────────────────────────────────────────────────

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)
    users = db.query(User).order_by(User.id.desc()).all()
    return [_to_user_response(db, u) for u in users]


@router.post("", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)

    email = payload.email.strip().lower()
    if "@" not in email:
        email = f"{email}@slt.com.lk"

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email}' already exists.",
        )

    try:
        role_enum = UserRole[payload.role.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {[r.name for r in UserRole]}",
        )

    # Determine the set of roles to grant from the optional roles list
    # If caller supplied a roles[] list, use that; otherwise fall back to single role field
    extra_roles: List[str] = payload.roles if payload.roles else [payload.role]

    # Resolve enums – validate every role before touching the DB
    try:
        extra_role_enums: List[UserRole] = [UserRole[r.upper()] for r in extra_roles]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {exc}. Must be one of: {[r.name for r in UserRole]}",
        )

    # Primary role = first in the list (or the role field when no list)
    primary_role_enum = extra_role_enums[0]

    new_user = User(email=email, role=primary_role_enum, is_active=payload.is_active)
    db.add(new_user)
    db.flush()  # get ID before adding grants

    # Build the full set of roles to grant (exactly what was requested — no auto-expansion)
    roles_to_grant: List[UserRole] = list(dict.fromkeys(extra_role_enums))  # deduplicated, order preserved

    granter_id: Optional[int] = current_user.id if current_user.id != 0 else None
    for r in roles_to_grant:
        grant = UserRoleGrant(user_id=new_user.id, role=r, granted_by=granter_id)
        db.add(grant)

    db.commit()
    db.refresh(new_user)
    return _to_user_response(db, new_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    db.delete(user)
    db.commit()
    return None


@router.patch("/{user_id}/roles", response_model=UserResponse)
def update_user_roles(
    user_id: int,
    payload: RoleUpdatePayload,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    """Replace all role grants for a user with the given set."""
    _require_manager(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Validate roles
    new_roles = []
    for r in payload.roles:
        try:
            new_roles.append(UserRole[r.upper()])
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {r}",
            )

    # Remove existing grants then re-add
    db.query(UserRoleGrant).filter(UserRoleGrant.user_id == user_id).delete()

    granter_id: Optional[int] = current_user.id if current_user.id != 0 else None
    for r in new_roles:
        db.add(UserRoleGrant(user_id=user_id, role=r, granted_by=granter_id))

    # Update primary role to first in list (or CUSTOMER if empty)
    if new_roles:
        user.role = new_roles[0]
    else:
        user.role = UserRole.CUSTOMER

    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


@router.get("/{user_id}/activity")
def get_user_activity(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    """Return role grant history for a user (activity log)."""
    _require_manager(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    grants = (
        db.query(UserRoleGrant)
        .filter(UserRoleGrant.user_id == user_id)
        .order_by(UserRoleGrant.granted_at.desc())
        .all()
    )

    # Also include approved permission requests for this email
    requests = (
        db.query(PermissionRequest)
        .filter(
            PermissionRequest.email == user.email,
            PermissionRequest.status == PermissionRequestStatus.APPROVED,
        )
        .order_by(PermissionRequest.reviewed_at.desc())
        .all()
    )

    return {
        "user_id": user_id,
        "email": user.email,
        "role_grants": [
            {
                "role": g.role.value,
                "granted_at": g.granted_at.isoformat() if g.granted_at else None,
            }
            for g in grants
        ],
        "approved_requests": [
            {
                "requested_roles": json.loads(r.requested_roles),
                "reason": r.reason,
                "approved_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
            for r in requests
        ],
    }


# ── Permission Request endpoints ─────────────────────────────────────────────

@router.post("/request-access", status_code=status.HTTP_201_CREATED)
def request_access(
    payload: AccessRequestPayload,
    db: Session = Depends(get_db),
):
    """
    Submit a permission/access request.
    This endpoint does NOT require the caller to be in the DB —
    a new Microsoft-authenticated user can call it with is_new_user=True.
    """
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email is required.",
        )

    if not payload.requested_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one role must be requested.",
        )

    # Validate role names
    for r in payload.requested_roles:
        try:
            UserRole[r.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {r}",
            )

    pr = PermissionRequest(
        email=email,
        requested_roles=json.dumps([r.upper() for r in payload.requested_roles]),
        reason=payload.reason,
        status=PermissionRequestStatus.PENDING,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)

    return {
        "id": pr.id,
        "message": "Access request submitted successfully. Please wait for manager approval.",
    }


@router.get("/permission-requests", response_model=List[PermissionRequestResponse])
def list_permission_requests(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)
    reqs = (
        db.query(PermissionRequest)
        .order_by(PermissionRequest.created_at.desc())
        .all()
    )
    return [
        PermissionRequestResponse(
            id=r.id,
            email=r.email,
            requested_roles=json.loads(r.requested_roles),
            reason=r.reason,
            status=r.status.value,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            rejection_note=r.rejection_note,
            created_at=r.created_at.isoformat(),
        )
        for r in reqs
    ]


@router.patch("/permission-requests/{request_id}/approve", response_model=PermissionRequestResponse)
def approve_permission_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)

    pr = db.query(PermissionRequest).filter(PermissionRequest.id == request_id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if pr.status != PermissionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be approved",
        )

    roles = json.loads(pr.requested_roles)
    granter_id: Optional[int] = current_user.id if current_user.id != 0 else None

    # Upsert user if not already in DB
    user = db.query(User).filter(User.email == pr.email).first()
    if user is None:
        primary_role_str = roles[0] if roles else "CUSTOMER"
        try:
            primary_role = UserRole[primary_role_str]
        except KeyError:
            primary_role = UserRole.CUSTOMER
        user = User(email=pr.email, role=primary_role, is_active=True)
        db.add(user)
        db.flush()

    # Grant each requested role
    for role_str in roles:
        try:
            role_enum = UserRole[role_str]
        except KeyError:
            continue
        existing = (
            db.query(UserRoleGrant)
            .filter(UserRoleGrant.user_id == user.id, UserRoleGrant.role == role_enum)
            .first()
        )
        if not existing:
            db.add(UserRoleGrant(user_id=user.id, role=role_enum, granted_by=granter_id))

    # If ADMIN granted, add all portal roles
    if "ADMIN" in roles:
        for extra_role in [UserRole.GMF_HANDLER, UserRole.ENVELOPE_HANDLER, UserRole.MANAGER]:
            existing = (
                db.query(UserRoleGrant)
                .filter(UserRoleGrant.user_id == user.id, UserRoleGrant.role == extra_role)
                .first()
            )
            if not existing:
                db.add(UserRoleGrant(user_id=user.id, role=extra_role, granted_by=granter_id))

    pr.status = PermissionRequestStatus.APPROVED
    pr.reviewed_by = granter_id
    pr.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pr)

    return PermissionRequestResponse(
        id=pr.id,
        email=pr.email,
        requested_roles=json.loads(pr.requested_roles),
        reason=pr.reason,
        status=pr.status.value,
        reviewed_at=pr.reviewed_at.isoformat() if pr.reviewed_at else None,
        rejection_note=pr.rejection_note,
        created_at=pr.created_at.isoformat(),
    )


@router.patch("/permission-requests/{request_id}/reject", response_model=PermissionRequestResponse)
def reject_permission_request(
    request_id: int,
    payload: RejectRequestPayload,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
):
    _require_manager(current_user)

    pr = db.query(PermissionRequest).filter(PermissionRequest.id == request_id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if pr.status != PermissionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be rejected",
        )

    pr.status = PermissionRequestStatus.REJECTED
    pr.reviewed_by = current_user.id if current_user.id != 0 else None
    pr.reviewed_at = datetime.now(timezone.utc)
    pr.rejection_note = payload.note
    db.commit()
    db.refresh(pr)

    return PermissionRequestResponse(
        id=pr.id,
        email=pr.email,
        requested_roles=json.loads(pr.requested_roles),
        reason=pr.reason,
        status=pr.status.value,
        reviewed_at=pr.reviewed_at.isoformat() if pr.reviewed_at else None,
        rejection_note=pr.rejection_note,
        created_at=pr.created_at.isoformat(),
    )
