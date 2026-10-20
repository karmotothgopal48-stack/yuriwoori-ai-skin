"""record recommendations_shown once per scan and product

Revision ID: d3a1f0c2b7e4
Revises: c59770c38ab1
Create Date: 2026-09-28 14:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3a1f0c2b7e4'
down_revision: Union[str, Sequence[str], None] = 'c59770c38ab1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Concurrent requests could insert the same "shown" rows twice; keep the earliest of each.
    op.execute("""
        DELETE FROM engagement_events e
        USING engagement_events keep
        WHERE e.event_type = 'recommendations_shown' AND keep.event_type = 'recommendations_shown'
          AND e.scan_id = keep.scan_id AND e.product_handle = keep.product_handle
          AND (e.created_at, e.id::text) > (keep.created_at, keep.id::text)
    """)
    op.create_index('uq_engagement_shown_once', 'engagement_events', ['scan_id', 'product_handle'], unique=True,
                    postgresql_where=sa.text("event_type = 'recommendations_shown'"))


def downgrade() -> None:
    op.drop_index('uq_engagement_shown_once', table_name='engagement_events',
                  postgresql_where=sa.text("event_type = 'recommendations_shown'"))
