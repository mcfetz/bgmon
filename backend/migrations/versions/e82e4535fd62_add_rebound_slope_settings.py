"""add rebound slope settings

Revision ID: e82e4535fd62
Revises: 3b4eb1cc9f48
Create Date: 2026-11-02 10:53:00.483162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e82e4535fd62'
down_revision = '3b4eb1cc9f48'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('global_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rebound_slope_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        batch_op.add_column(sa.Column('rebound_slope_threshold_mgdl_per_min', sa.Float(), nullable=False, server_default=sa.text('1.8')))
        batch_op.add_column(sa.Column('rebound_slope_window_minutes', sa.Integer(), nullable=False, server_default=sa.text('30')))
        batch_op.add_column(sa.Column('rebound_rise_floor_mgdl', sa.Integer(), nullable=False, server_default=sa.text('80')))
        batch_op.add_column(sa.Column('rebound_max_age_after_low_minutes', sa.Integer(), nullable=False, server_default=sa.text('120')))
        batch_op.add_column(sa.Column('rebound_alert_with_carbs', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade():
    with op.batch_alter_table('global_settings', schema=None) as batch_op:
        batch_op.drop_column('rebound_alert_with_carbs')
        batch_op.drop_column('rebound_max_age_after_low_minutes')
        batch_op.drop_column('rebound_rise_floor_mgdl')
        batch_op.drop_column('rebound_slope_window_minutes')
        batch_op.drop_column('rebound_slope_threshold_mgdl_per_min')
        batch_op.drop_column('rebound_slope_enabled')
