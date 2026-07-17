"""expand legacy stats dashboard tile

Revision ID: 20260717_010000
Revises: 20260717_000000
Create Date: 2026-07-17 01:00:00.000000
"""

from alembic import op


revision = "20260717_010000"
down_revision = "20260717_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET dashboard_tiles = (
            (dashboard_tiles - 'stats') ||
            '["daily-score", "prediction", "tir", "streak", "min-mean-max", "badges", "gmi", "readings"]'::jsonb
        )
        WHERE dashboard_tiles ? 'stats'
        """
    )


def downgrade() -> None:
    pass
