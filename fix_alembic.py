from app.db.base import engine
from sqlalchemy import text
with engine.begin() as conn:
    conn.execute(text("UPDATE alembic_version SET version_num = 'a2c3d4e5f607'"))
    print("Updated alembic_version to a2c3d4e5f607")
