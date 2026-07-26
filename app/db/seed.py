"""
Synthetic seed data for the SLT e-bill system.

Usage:  python -m app.db.seed
"""

from __future__ import annotations

import sys
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.logging import configure_logging, get_logger
from app.db.base import SessionLocal
from app.db.models import UserRole

log = get_logger(__name__)

def seed_admin(session: Session) -> None:
    admin_email = "admin@slt.lk"
    admin = session.query(User).filter(User.email == admin_email).first()
    
    if not admin:
        log.info(f"Creating default admin user: {admin_email}")
        admin = User(
            email=admin_email,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
    else:
        log.info(f"Admin user {admin_email} already exists.")

    gmf_email = "gmf@slt.lk"
    gmf = session.query(User).filter(User.email == gmf_email).first()
    if not gmf:
        log.info(f"Creating default GMF Handler user: {gmf_email}")
        gmf = User(
            email=gmf_email,
            role=UserRole.GMF_HANDLER,
            is_active=True,
        )
        session.add(gmf)
    else:
        log.info(f"GMF Handler user {gmf_email} already exists.")

    manager_email = "manager@slt.lk"
    manager = session.query(User).filter(User.email == manager_email).first()
    if not manager:
        log.info(f"Creating default Manager user: {manager_email}")
        manager = User(
            email=manager_email,
            role=UserRole.MANAGER,
            is_active=True,
        )
        session.add(manager)
    else:
        log.info(f"Manager user {manager_email} already exists.")
        
    session.commit()

def main() -> int:
    configure_logging()
    log.info("Starting database seed...")

    try:
        with SessionLocal() as session:
            seed_admin(session)
            log.info("Database seeding complete.")
    except Exception as e:
        log.error(f"Seeding failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
