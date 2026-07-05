"""add notification_profiles tables

Revision ID: 20260629_250000
Revises: 20260629_240000
Create Date: 2026-06-29 25:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = '20260629_250000'
down_revision = '20260629_240000'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DO $$ BEGIN CREATE TYPE notification_area AS ENUM ('silent', 'push', 'call'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE notification_threshold AS ENUM ('critical_low', 'low', 'high', 'critical_high'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if 'notification_profiles' not in existing_tables:
        op.create_table(
            'notification_profiles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if 'notification_assignments' not in existing_tables:
        op.create_table(
            'notification_assignments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('profile_id', sa.Integer(), sa.ForeignKey('notification_profiles.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('area', sa.Enum('silent', 'push', 'call', name='notification_area', create_type=False), nullable=False),
            sa.Column('threshold', sa.Enum('critical_low', 'low', 'high', 'critical_high', name='notification_threshold', create_type=False), nullable=False),
            sa.UniqueConstraint('profile_id', 'threshold', name='uq_profile_threshold'),
        )


def downgrade():
    op.drop_table('notification_assignments')
    op.drop_table('notification_profiles')
    op.execute("DROP TYPE IF EXISTS notification_threshold")
    op.execute("DROP TYPE IF EXISTS notification_area")
