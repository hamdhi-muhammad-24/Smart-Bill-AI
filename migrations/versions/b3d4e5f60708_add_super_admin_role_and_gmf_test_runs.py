"""add super_admin role and gmf_test_runs table

Revision ID: b3d4e5f60708
Revises: a2c3d4e5f607
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b3d4e5f60708'
down_revision: Union[str, Sequence[str], None] = 'a2c3d4e5f607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")
        op.execute(
            "DO $enum$ BEGIN "
            "CREATE TYPE gmf_test_run_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $enum$;"
        )

    status_enum = postgresql.ENUM('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='gmf_test_run_status', create_type=False)

    op.create_table(
        'gmf_test_runs',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('status', status_enum, nullable=False, server_default='PENDING'),
        sa.Column('triggered_by', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_files_sampled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_invoices_tested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('passed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('results_json', sa.Text(), nullable=True),
        sa.Column('report_pdf_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('gmf_test_runs')
