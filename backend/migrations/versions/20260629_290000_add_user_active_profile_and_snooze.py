"""add user_active_profiles and user_snoozes tables

Revision ID: 20260629_290000
Revises: 20260629_280000
Create Date: 2026-06-29 29:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = '20260629_290000'
down_revision = '20260629_280000'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_active_profiles',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('notification_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'user_snoozes',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('snooze_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('user_snoozes')
    op.drop_table('user_active_profiles')
