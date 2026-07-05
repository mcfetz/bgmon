"""fix notification_threshold enum to uppercase

Same fix as notification_area: initial migration created lowercase values,
SQLAlchemy sends member names (uppercase). Recreate enum with uppercase.

Revision ID: 20260629_280000
Revises: 20260629_270000
Create Date: 2026-06-29 28:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = '20260629_280000'
down_revision = '20260629_270000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sa.text("SELECT typname FROM pg_type WHERE typname IN ('notification_threshold', 'notification_threshold_old')"))}
    if 'notification_threshold' not in existing:
        return
    if 'notification_threshold_old' in existing:
        op.execute("DROP TYPE IF EXISTS notification_threshold_old")
    op.execute("ALTER TYPE notification_threshold RENAME TO notification_threshold_old")
    op.execute("CREATE TYPE notification_threshold AS ENUM ('CRITICAL_LOW', 'LOW', 'HIGH', 'CRITICAL_HIGH')")
    op.execute("""
        ALTER TABLE notification_assignments
        ALTER COLUMN threshold DROP DEFAULT,
        ALTER COLUMN threshold TYPE notification_threshold
        USING (
            CASE threshold::text
                WHEN 'critical_low' THEN 'CRITICAL_LOW'::notification_threshold
                WHEN 'low' THEN 'LOW'::notification_threshold
                WHEN 'high' THEN 'HIGH'::notification_threshold
                WHEN 'critical_high' THEN 'CRITICAL_HIGH'::notification_threshold
                WHEN 'CRITICAL_LOW' THEN 'CRITICAL_LOW'::notification_threshold
                WHEN 'LOW' THEN 'LOW'::notification_threshold
                WHEN 'HIGH' THEN 'HIGH'::notification_threshold
                WHEN 'CRITICAL_HIGH' THEN 'CRITICAL_HIGH'::notification_threshold
            END
        )
    """)
    op.execute("DROP TYPE notification_threshold_old")


def downgrade():
    op.execute("ALTER TYPE notification_threshold RENAME TO notification_threshold_old")
    op.execute("CREATE TYPE notification_threshold AS ENUM ('critical_low', 'low', 'high', 'critical_high')")
    op.execute("""
        ALTER TABLE notification_assignments
        ALTER COLUMN threshold TYPE notification_threshold
        USING (
            CASE threshold::text
                WHEN 'CRITICAL_LOW' THEN 'critical_low'::notification_threshold
                WHEN 'LOW' THEN 'low'::notification_threshold
                WHEN 'HIGH' THEN 'high'::notification_threshold
                WHEN 'CRITICAL_HIGH' THEN 'critical_high'::notification_threshold
            END
        )
    """)
    op.execute("DROP TYPE notification_threshold_old")
