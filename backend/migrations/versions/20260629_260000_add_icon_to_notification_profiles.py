"""add icon to notification_profiles

Revision ID: 20260629_260000
Revises: 20260629_250000
Create Date: 2026-06-29 26:00:00

"""

from alembic import op


revision = '20260629_260000'
down_revision = '20260629_250000'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE notification_profiles ADD COLUMN IF NOT EXISTS icon VARCHAR(10)")
    op.execute("UPDATE notification_profiles SET icon = '🔔' WHERE icon IS NULL")
    op.execute("ALTER TABLE notification_profiles ALTER COLUMN icon SET NOT NULL")


def downgrade():
    op.drop_column('notification_profiles', 'icon')
