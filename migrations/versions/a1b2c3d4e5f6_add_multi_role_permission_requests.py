"""add user_role_grants and permission_requests tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'e8f9a0b1c2d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute("COMMIT")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMIN1'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'GMF_HANDLER'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ENVELOPE_HANDLER'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'MANAGER'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'CUSTOMER'")
        op.execute("BEGIN")

    # Create permission_request_status enum safely
    op.execute(
        "DO $prs$ BEGIN "
        "CREATE TYPE permission_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $prs$;"
    )

    # Create user_role_grants junction table
    op.create_table(
        'user_role_grants',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('user_id', sa.BigInteger(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role',
                  postgresql.ENUM('ADMIN', 'ADMIN1', 'GMF_HANDLER', 'ENVELOPE_HANDLER',
                          'MANAGER', 'CUSTOMER', name='user_role', create_type=False),
                  nullable=False),
        sa.Column('granted_by', sa.BigInteger(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'role', name='uq_user_role_grant'),
    )

    # Create permission_requests table
    op.create_table(
        'permission_requests',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('requested_roles', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status',
                  postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED',
                          name='permission_request_status', create_type=False),
                  nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', sa.BigInteger(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    # ── Seed testuser016 as ADMIN ──────────────────────────────────────────
    op.execute(
        "INSERT INTO users (email, role, is_active) "
        "VALUES ('testuser016@intranet.slt.com.lk', 'ADMIN', true) "
        "ON CONFLICT (email) DO UPDATE SET role = 'ADMIN', is_active = true;"
    )

    # Grant all portal roles to testuser016
    op.execute(
        "WITH u AS (SELECT id FROM users WHERE email = 'testuser016@intranet.slt.com.lk') "
        "INSERT INTO user_role_grants (user_id, role) "
        "SELECT u.id, r.role FROM u, "
        "(VALUES ('ADMIN'::user_role), ('GMF_HANDLER'::user_role), ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role) "
        "ON CONFLICT (user_id, role) DO NOTHING;"
    )

    # ── Backfill existing users with their current role ────────────────────
    op.execute(
        "INSERT INTO user_role_grants (user_id, role) "
        "SELECT id, role FROM users "
        "WHERE role != 'CUSTOMER' "
        "ON CONFLICT (user_id, role) DO NOTHING;"
    )

    # Grant all portal roles to all existing ADMIN users
    op.execute(
        "WITH admins AS (SELECT id FROM users WHERE role = 'ADMIN') "
        "INSERT INTO user_role_grants (user_id, role) "
        "SELECT a.id, r.role FROM admins a, "
        "(VALUES ('GMF_HANDLER'::user_role), ('ENVELOPE_HANDLER'::user_role), ('MANAGER'::user_role)) AS r(role) "
        "ON CONFLICT (user_id, role) DO NOTHING;"
    )


def downgrade() -> None:
    op.drop_table('permission_requests')
    op.drop_table('user_role_grants')
    op.execute('DROP TYPE IF EXISTS permission_request_status;')
