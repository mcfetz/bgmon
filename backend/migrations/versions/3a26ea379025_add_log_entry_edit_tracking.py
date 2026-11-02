"""add log entry edit tracking

Revision ID: 3a26ea379025
Revises: e82e4535fd62
Create Date: 2026-11-02 20:30:44.005851

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a26ea379025'
down_revision = 'e82e4535fd62'
branch_labels = None
depends_on = None

FK_NAME = 'fk_log_entries_updated_by_id_users'


def upgrade():
    with op.batch_alter_table('log_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('updated_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            FK_NAME, 'users', ['updated_by_id'], ['id'], ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('log_entries', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')
        batch_op.drop_column('updated_by_id')
        batch_op.drop_column('updated_at')
