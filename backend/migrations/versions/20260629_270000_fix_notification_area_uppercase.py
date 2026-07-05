"""fix notification_area enum to uppercase PUSH CALL

Initial migration created enum with lowercase values, but SQLAlchemy sends
member names (uppercase). This migration recreates the enum to match.

Revision ID: 20260629_270000
Revises: 20260629_260000
Create Date: 2026-06-29 27:00:00

"""

from alembic import op


revision = '20260629_270000'
down_revision = '20260629_260000'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE notification_area RENAME TO notification_area_old")
    op.execute("CREATE TYPE notification_area AS ENUM ('PUSH', 'CALL')")
    op.execute("""
        ALTER TABLE notification_assignments
        ALTER COLUMN area DROP DEFAULT,
        ALTER COLUMN area TYPE notification_area
        USING (
            CASE area::text
                WHEN 'push' THEN 'PUSH'::notification_area
                WHEN 'call' THEN 'CALL'::notification_area
                WHEN 'silent' THEN 'PUSH'::notification_area
                WHEN 'PUSH' THEN 'PUSH'::notification_area
                WHEN 'CALL' THEN 'CALL'::notification_area
            END
        )
    """)
    op.execute("DROP TYPE notification_area_old")


def downgrade():
    op.execute("ALTER TYPE notification_area RENAME TO notification_area_old")
    op.execute("CREATE TYPE notification_area AS ENUM ('push', 'call')")
    op.execute("""
        ALTER TABLE notification_assignments
        ALTER COLUMN area TYPE notification_area
        USING (
            CASE area::text
                WHEN 'PUSH' THEN 'push'::notification_area
                WHEN 'CALL' THEN 'call'::notification_area
            END
        )
    """)
    op.execute("DROP TYPE notification_area_old")
