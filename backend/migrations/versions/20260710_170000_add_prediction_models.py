"""add prediction persistence models

Revision ID: 20260710_170000
Revises: 20260710_000000
Create Date: 2026-07-10 17:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_170000"
down_revision: str | None = "20260710_000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prediction_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("context_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("feature_version", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_runs_user_id", "prediction_runs", ["user_id"])
    op.create_index("ix_prediction_runs_generated_at", "prediction_runs", ["generated_at"])
    op.create_index("ix_prediction_runs_horizon_minutes", "prediction_runs", ["horizon_minutes"])

    op.create_table(
        "prediction_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_sgv", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=True),
        sa.Column("upper_bound", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["prediction_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "timestamp", name="uq_prediction_point_run_ts"),
    )
    op.create_index("ix_prediction_points_run_id", "prediction_points", ["run_id"])
    op.create_index("ix_prediction_points_timestamp", "prediction_points", ["timestamp"])


def downgrade() -> None:
    op.drop_table("prediction_points")
    op.drop_table("prediction_runs")
