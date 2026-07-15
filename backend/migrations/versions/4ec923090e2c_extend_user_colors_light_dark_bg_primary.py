"""extend user colors: light/dark bg + primary

Revision ID: 4ec923090e2c
Revises: e49ca9a43f28
Create Date: 2026-07-15 20:10:20.199210

"""
from alembic import op
import sqlalchemy as sa


revision = '4ec923090e2c'
down_revision = 'e49ca9a43f28'
branch_labels = None
depends_on = None


def upgrade():
    # Rename existing columns
    op.execute("ALTER TABLE users RENAME COLUMN color_bg TO color_bg_light")
    op.execute("ALTER TABLE users RENAME COLUMN color_primary TO color_primary_light")
    # Add dark variants
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('color_bg_dark', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('color_primary_dark', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('color_primary_dark')
        batch_op.drop_column('color_bg_dark')
    op.execute("ALTER TABLE users RENAME COLUMN color_bg_light TO color_bg")
    op.execute("ALTER TABLE users RENAME COLUMN color_primary_light TO color_primary")
