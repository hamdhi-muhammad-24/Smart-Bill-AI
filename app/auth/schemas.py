from typing import List
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str                          # primary / legacy role
    roles: List[str] = []              # all granted portal roles
    is_new_user: bool = False          # True when email not in DB at all


class PdfTokenOut(BaseModel):
    token: str
    expires_in: int

