"""add twilio_from_number to users

Revision ID: 20260629_240000
Revises: 02e0084e3298
Create Date: 2026-06-29 24:00:00

"""

from alembic import op


revision = '20260629_240000'
down_revision = '02e0084e3298'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS twilio_from_number VARCHAR(20)")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS twilio_from_number")
