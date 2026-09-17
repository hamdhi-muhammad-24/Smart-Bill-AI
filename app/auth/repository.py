from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    if not email:
        return None
    clean_email = email.strip().lower()
    return db.scalar(select(User).where(func.lower(User.email) == clean_email))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
