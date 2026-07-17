"""add dashboard_tiles jsonb column to users

Revision ID: 20260717_000000
Revises: 4ec923090e2c
Create Date: 2026-07-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = '20260717_000000'
down_revision = '4ec923090e2c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('dashboard_tiles', JSON(none_as_null=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('dashboard_tiles')
