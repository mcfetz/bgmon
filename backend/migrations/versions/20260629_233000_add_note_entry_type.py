"""add note entry type to log_entry_type enum

Revision ID: 20260629_233000
Revises: 02e0084e3298
Create Date: 2026-06-29 23:30:00

"""

from alembic import op


revision = '20260629_233000'
down_revision = '02e0084e3298'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE log_entry_type ADD VALUE IF NOT EXISTS 'note'")


def downgrade():
    op.execute("ALTER TYPE log_entry_type DROP VALUE 'note'")
