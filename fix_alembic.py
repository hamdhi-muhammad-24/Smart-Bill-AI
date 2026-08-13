from app.db.base import engine
from sqlalchemy import text
with engine.begin() as conn:
    conn.execute(text("UPDATE alembic_version SET version_num = 'e8f9a0b1c2d4'"))
    print("Updated alembic_version")
