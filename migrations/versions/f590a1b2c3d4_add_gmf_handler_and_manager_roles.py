"""add gmf_handler and manager to user_role enum

Revision ID: f590a1b2c3d4
Revises: f481e0ff17ec
Create Date: 2026-07-26 06:11:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f590a1b2c3d4'
down_revision = 'f481e0ff17ec'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'GMF_HANDLER'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'MANAGER'")

def downgrade():
    pass
