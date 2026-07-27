"""add gmf upload record counts

Revision ID: e8f9a0b1c2d4
Revises: f590a1b2c3d4
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = 'e8f9a0b1c2d4'
down_revision = 'f590a1b2c3d4'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('gmf_uploads', sa.Column('processed_records_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('gmf_uploads', sa.Column('total_records_count', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:
    op.drop_column('gmf_uploads', 'total_records_count')
    op.drop_column('gmf_uploads', 'processed_records_count')
