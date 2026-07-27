"""add SUCCESS to log_entry_type enum

Revision ID: 20260727_000000
Revises: cb79d170d256
Create Date: 2026-07-27 00:00:00

"""
from alembic import op


revision = '20260727_000000'
down_revision = 'cb79d170d256'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE log_entry_type ADD VALUE IF NOT EXISTS 'SUCCESS'")


def downgrade():
    op.execute("ALTER TYPE log_entry_type DROP VALUE 'SUCCESS'")