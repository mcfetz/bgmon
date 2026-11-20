"""add basal reminder threshold and no_basal alarms

- thresholds.basal_reminder_time (per-user reminder time, Europe/Berlin)
- alarm_type enum gains NO_BASAL
- notification_threshold enum gains NO_BASAL for profile assignments

Revision ID: 20261120_000000
Revises: 3a26ea379025
Create Date: 2026-11-20 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '20261120_000000'
down_revision = '3a26ea379025'
branch_labels = None
depends_on = None

_ENUM_VALUES = {
    'alarm_type': ['CRITICAL_LOW', 'LOW', 'HIGH', 'CRITICAL_HIGH', 'NO_DATA'],
    'notification_threshold': ['CRITICAL_LOW', 'LOW', 'HIGH', 'CRITICAL_HIGH', 'NO_DATA'],
}
_ENUM_COLUMNS = {
    'alarm_type': ('alarms', 'alarm_type'),
    'notification_threshold': ('notification_assignments', 'threshold'),
}


def upgrade():
    op.execute("ALTER TYPE alarm_type ADD VALUE IF NOT EXISTS 'NO_BASAL'")
    op.execute("ALTER TYPE notification_threshold ADD VALUE IF NOT EXISTS 'NO_BASAL'")

    insp = sa.inspect(op.get_bind())
    columns = {c['name'] for c in insp.get_columns('thresholds')}
    if 'basal_reminder_time' not in columns:
        op.add_column(
            'thresholds',
            sa.Column('basal_reminder_time', sa.String(length=5), nullable=True),
        )


def downgrade():
    # Rows using the new enum value must go before the type can lose it.
    op.execute("DELETE FROM alarms WHERE alarm_type = 'NO_BASAL'")
    op.execute("DELETE FROM notification_assignments WHERE threshold = 'NO_BASAL'")

    for enum_name, values in _ENUM_VALUES.items():
        table, column = _ENUM_COLUMNS[enum_name]
        old_name = f"{enum_name}_old"
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {old_name}")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({', '.join(repr(v) for v in values)})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {enum_name} "
            f"USING {column}::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {old_name}")

    op.drop_column('thresholds', 'basal_reminder_time')
