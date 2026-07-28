"""add composite index for prediction history queries

Revision ID: 20260728_000000
Revises: bf107c9aa9bd
Create Date: 2026-07-28 00:00:00

"""
from alembic import op


revision = '20260728_000000'
down_revision = 'bf107c9aa9bd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_prediction_runs_user_horizon",
        "prediction_runs",
        ["user_id", "horizon_minutes"],
    )


def downgrade():
    op.drop_index("ix_prediction_runs_user_horizon", table_name="prediction_runs")
