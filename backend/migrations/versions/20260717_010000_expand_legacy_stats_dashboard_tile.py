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
        WITH target AS (
            SELECT id, dashboard_tiles::jsonb AS tiles
            FROM users
            WHERE dashboard_tiles IS NOT NULL
              AND jsonb_typeof(dashboard_tiles::jsonb) = 'array'
              AND dashboard_tiles::jsonb ? 'stats'
        ), expanded AS (
            SELECT t.id, (
                SELECT jsonb_agg(to_jsonb(x.tile) ORDER BY x.sort_key)
                FROM (
                    SELECT element.value AS tile, element.ordinality AS sort_key
                    FROM jsonb_array_elements_text(t.tiles) WITH ORDINALITY AS element(value, ordinality)
                    WHERE element.value <> 'stats'

                    UNION ALL

                    SELECT expanded_tile.tile, 1000 + expanded_tile.ordinality AS sort_key
                    FROM (
                        VALUES
                            ('daily-score', 1),
                            ('prediction', 2),
                            ('tir', 3),
                            ('streak', 4),
                            ('min-mean-max', 5),
                            ('badges', 6),
                            ('gmi', 7),
                            ('readings', 8)
                    ) AS expanded_tile(tile, ordinality)
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(t.tiles) AS existing(value)
                        WHERE existing.value = expanded_tile.tile
                    )
                ) AS x
            ) AS new_tiles
            FROM target AS t
        )
        UPDATE users AS u
        SET dashboard_tiles = expanded.new_tiles::json
        FROM expanded
        WHERE u.id = expanded.id
        """
    )


def downgrade() -> None:
    pass
