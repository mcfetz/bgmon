"""add performance indexes

Revision ID: 20260710_000000
Revises: 20260703_150000
Create Date: 2026-07-10 00:00:00

"""
from alembic import op

revision = "20260710_000000"
down_revision = "20260703_150000"
branch_labels = None
depends_on = None


def upgrade():
    # alarms: filtered by (user_id, alarm_type, acknowledged_at) in alarm evaluator
    op.create_index(
        "ix_alarms_eval",
        "alarms",
        ["user_id", "alarm_type", "acknowledged_at"],
    )

    # log_entries: filtered by user_id + created_at range in dashboard/log queries
    op.create_index(
        "ix_log_entries_user_created",
        "log_entries",
        ["user_id", "created_at"],
    )

    # log_entries: filtered by user_id + entry_type in streak/score calculations
    op.create_index(
        "ix_log_entries_user_type",
        "log_entries",
        ["user_id", "entry_type"],
    )

    # shifts: filtered by active status
    op.create_index(
        "ix_shifts_active",
        "shifts",
        ["active"],
    )

    # basal_rate_history: filtered by user_id + ordered by changed_at
    op.create_index(
        "ix_basal_rate_history_user_changed",
        "basal_rate_history",
        ["user_id", "changed_at"],
    )

    # carb_factor_history: same pattern as basal_rate_history
    op.create_index(
        "ix_carb_factor_history_user_changed",
        "carb_factor_history",
        ["user_id", "changed_at"],
    )

    # push_subscriptions: filtered by endpoint for unsubscribe
    op.create_index(
        "ix_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint"],
    )


def downgrade():
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("ix_carb_factor_history_user_changed", table_name="carb_factor_history")
    op.drop_index("ix_basal_rate_history_user_changed", table_name="basal_rate_history")
    op.drop_index("ix_shifts_active", table_name="shifts")
    op.drop_index("ix_log_entries_user_type", table_name="log_entries")
    op.drop_index("ix_log_entries_user_created", table_name="log_entries")
    op.drop_index("ix_alarms_eval", table_name="alarms")
