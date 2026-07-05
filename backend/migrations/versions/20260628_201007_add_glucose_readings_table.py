"""add glucose_readings table

Revision ID: 20260628_201007
Revises:
Create Date: 2026-06-28 20:10:07

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260628_201007'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'glucose_readings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sgv', sa.Integer(), nullable=False),
        sa.Column('trend', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(30), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='librelinkup'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_glucose_readings_timestamp', 'glucose_readings', ['timestamp'])
    op.create_unique_constraint('uq_glucose_readings_timestamp', 'glucose_readings', ['timestamp'])


def downgrade():
    op.drop_table('glucose_readings')
