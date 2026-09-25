"""add stock_set_at timestamps

Revision ID: 1b6c62c32786
Revises: b18b80f7b36e
Create Date: 2026-09-25 19:57:48.136701

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b6c62c32786'
down_revision = 'b18b80f7b36e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('global_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('insulin_stock_set_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('basal_stock_set_at', sa.DateTime(timezone=True), nullable=True))

    # Existing stock values have no recorded count time; assume they were
    # counted the moment this feature ships so consumption counting works
    # immediately instead of waiting for a re-enter.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            'UPDATE global_settings SET insulin_stock_set_at = now() '
            'WHERE insulin_stock IS NOT NULL AND insulin_stock_set_at IS NULL'
        )
    )
    conn.execute(
        sa.text(
            'UPDATE global_settings SET basal_stock_set_at = now() '
            'WHERE basal_stock IS NOT NULL AND basal_stock_set_at IS NULL'
        )
    )


def downgrade():
    with op.batch_alter_table('global_settings', schema=None) as batch_op:
        batch_op.drop_column('basal_stock_set_at')
        batch_op.drop_column('insulin_stock_set_at')
