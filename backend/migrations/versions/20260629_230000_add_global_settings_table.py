"""add global_settings table

Revision ID: 20260629_230000
Revises: 20260628_201007
Create Date: 2026-06-29 23:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = '20260629_230000'
down_revision = '20260628_201007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'global_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('insulin_action_hours', sa.Float(), nullable=False, server_default='4.0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("INSERT INTO global_settings (insulin_action_hours) VALUES (4.0)")


def downgrade():
    op.drop_table('global_settings')
