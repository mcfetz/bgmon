"""add alarm entry type

Revision ID: 20260703_150000
Revises: 5d6da09005e7
Create Date: 2026-07-03 15:00:00

"""
from alembic import op


revision = '20260703_150000'
down_revision = '5d6da09005e7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE log_entry_type RENAME TO log_entry_type_old")
    op.execute("CREATE TYPE log_entry_type AS ENUM ('CARBS', 'INSULIN', 'BASAL', 'NOTE', 'ALARM')")
    op.execute("""
        ALTER TABLE log_entries
        ALTER COLUMN entry_type TYPE log_entry_type
        USING (
            CASE entry_type::text
                WHEN 'carbs' THEN 'CARBS'::log_entry_type
                WHEN 'insulin' THEN 'INSULIN'::log_entry_type
                WHEN 'basal' THEN 'BASAL'::log_entry_type
                WHEN 'note' THEN 'NOTE'::log_entry_type
                WHEN 'alarm' THEN 'ALARM'::log_entry_type
                WHEN 'CARBS' THEN 'CARBS'::log_entry_type
                WHEN 'INSULIN' THEN 'INSULIN'::log_entry_type
                WHEN 'BASAL' THEN 'BASAL'::log_entry_type
                WHEN 'NOTE' THEN 'NOTE'::log_entry_type
                WHEN 'ALARM' THEN 'ALARM'::log_entry_type
            END
        )
    """)
    op.execute("DROP TYPE log_entry_type_old")


def downgrade():
    op.execute("ALTER TYPE log_entry_type RENAME TO log_entry_type_old")
    op.execute("CREATE TYPE log_entry_type AS ENUM ('CARBS', 'INSULIN', 'BASAL', 'NOTE')")
    op.execute("""
        ALTER TABLE log_entries
        ALTER COLUMN entry_type TYPE log_entry_type
        USING (
            CASE entry_type::text
                WHEN 'CARBS' THEN 'CARBS'::log_entry_type
                WHEN 'INSULIN' THEN 'INSULIN'::log_entry_type
                WHEN 'BASAL' THEN 'BASAL'::log_entry_type
                WHEN 'NOTE' THEN 'NOTE'::log_entry_type
                WHEN 'ALARM' THEN 'NOTE'::log_entry_type
            END
        )
    """)
    op.execute("DROP TYPE log_entry_type_old")
