"""add envelope_templates, envelope_artworks, and envelope_history tables

Revision ID: a2c3d4e5f607
Revises: 002f69064636
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2c3d4e5f607'
down_revision: Union[str, Sequence[str], None] = '002f69064636'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute(
            "DO $enum$ BEGIN "
            "CREATE TYPE envelope_type_enum AS ENUM ('LARGE', 'MEDIUM', 'SELF_SEAL'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $enum$;"
        )
        op.execute(
            "DO $enum$ BEGIN "
            "CREATE TYPE envelope_artwork_status_enum AS ENUM ('ACTIVE', 'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'REPLACED', 'REMOVED'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $enum$;"
        )

    op.create_table(
        'envelope_templates',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('envelope_type', postgresql.ENUM('LARGE', 'MEDIUM', 'SELF_SEAL', name='envelope_type_enum', create_type=False), nullable=False, unique=True),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('base_pdf_path', sa.Text(), nullable=False),
        sa.Column('box_x0', sa.Float(), nullable=True),
        sa.Column('box_y0', sa.Float(), nullable=True),
        sa.Column('box_x1', sa.Float(), nullable=True),
        sa.Column('box_y1', sa.Float(), nullable=True),
        sa.Column('rotation_deg', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fit_mode', sa.Text(), nullable=False, server_default='cover'),
        sa.Column('min_width', sa.Integer(), nullable=False, server_default='800'),
        sa.Column('min_height', sa.Integer(), nullable=False, server_default='250'),
        sa.Column('aspect_min', sa.Integer(), nullable=False, server_default='70'),
        sa.Column('aspect_max', sa.Integer(), nullable=False, server_default='350'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_table(
        'envelope_artworks',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('envelope_template_id', sa.BigInteger(), sa.ForeignKey('envelope_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('campaign_name', sa.Text(), nullable=True),
        sa.Column('image_path', sa.Text(), nullable=False),
        sa.Column('image_width', sa.Integer(), nullable=False),
        sa.Column('image_height', sa.Integer(), nullable=False),
        sa.Column('output_pdf_path', sa.Text(), nullable=True),
        sa.Column('preview_png_path', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('ACTIVE', 'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'REPLACED', 'REMOVED', name='envelope_artwork_status_enum', create_type=False), nullable=False, server_default='ACTIVE'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('replaced_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'envelope_history',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('template_name', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('envelope_history')
    op.drop_table('envelope_artworks')
    op.drop_table('envelope_templates')
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS envelope_artwork_status_enum')
        op.execute('DROP TYPE IF EXISTS envelope_type_enum')
