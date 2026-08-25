"""add no-data alarm configuration

- thresholds.no_data_after_minutes (per-user stale-data window)
- notification_threshold enum gains NO_DATA for profile assignments

Revision ID: 20260824_000000
Revises: cf648bc840c6
Create Date: 2026-08-24 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '20260824_000000'
down_revision = 'cf648bc840c6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_types = {
        row[0]
        for row in bind.execute(
            sa.text("SELECT typname FROM pg_type WHERE typname IN ('notification_threshold')")
        )
    }
    if 'notification_threshold' in existing_types:
        op.execute("ALTER TYPE notification_threshold ADD VALUE IF NOT EXISTS 'NO_DATA'")

    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    if 'thresholds' in existing_tables:
        columns = {c['name'] for c in insp.get_columns('thresholds')}
        if 'no_data_after_minutes' not in columns:
            op.add_column(
                'thresholds',
                sa.Column(
                    'no_data_after_minutes',
                    sa.Integer(),
                    server_default=sa.text('15'),
                    nullable=False,
                ),
            )


def downgrade():
    op.execute("ALTER TYPE notification_threshold DROP VALUE IF NOT EXISTS 'NO_DATA'")
    op.drop_column('thresholds', 'no_data_after_minutes')