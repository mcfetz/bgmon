"""fix note enum value to uppercase NOTE

The initial migration created log_entry_type enum with UPPERCASE values
('CARBS', 'INSULIN', 'BASAL'). SQLAlchemy sends the member name (uppercase).
The previous migration added 'note' (lowercase) which doesn't match.
This migration drops 'note' and adds 'NOTE' (uppercase).

Revision ID: 20260629_233500
Revises: 20260629_233000
Create Date: 2026-06-29 23:35:00

"""

from alembic import op


revision = '20260629_233500'
down_revision = '20260629_233000'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE log_entry_type RENAME TO log_entry_type_old")
    op.execute("CREATE TYPE log_entry_type AS ENUM ('CARBS', 'INSULIN', 'BASAL', 'NOTE')")
    op.execute("""
        ALTER TABLE log_entries
        ALTER COLUMN entry_type TYPE log_entry_type
        USING (
            CASE entry_type::text
                WHEN 'carbs' THEN 'CARBS'::log_entry_type
                WHEN 'insulin' THEN 'INSULIN'::log_entry_type
                WHEN 'basal' THEN 'BASAL'::log_entry_type
                WHEN 'note' THEN 'NOTE'::log_entry_type
                WHEN 'CARBS' THEN 'CARBS'::log_entry_type
                WHEN 'INSULIN' THEN 'INSULIN'::log_entry_type
                WHEN 'BASAL' THEN 'BASAL'::log_entry_type
                WHEN 'NOTE' THEN 'NOTE'::log_entry_type
            END
        )
    """)
    op.execute("DROP TYPE log_entry_type_old")


def downgrade():
    op.execute("ALTER TYPE log_entry_type RENAME TO log_entry_type_old")
    op.execute("CREATE TYPE log_entry_type AS ENUM ('CARBS', 'INSULIN', 'BASAL', 'note')")
    op.execute("""
        ALTER TABLE log_entries
        ALTER COLUMN entry_type TYPE log_entry_type
        USING (
            CASE entry_type::text
                WHEN 'carbs' THEN 'CARBS'::log_entry_type
                WHEN 'insulin' THEN 'INSULIN'::log_entry_type
                WHEN 'basal' THEN 'BASAL'::log_entry_type
                WHEN 'note' THEN 'note'::log_entry_type
                WHEN 'CARBS' THEN 'CARBS'::log_entry_type
                WHEN 'INSULIN' THEN 'INSULIN'::log_entry_type
                WHEN 'BASAL' THEN 'BASAL'::log_entry_type
                WHEN 'NOTE' THEN 'note'::log_entry_type
            END
        )
    """)
    op.execute("DROP TYPE log_entry_type_old")
