"""reports are built in memory: reports.content becomes optional; WhatsApp media id kept until deleted (additive)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-19 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New reports keep no content (it is generated when sent or opened). Existing content is NOT touched: the reports
    # made before keep it exactly as it is (owner's decision).
    op.alter_column('reports', 'content', existing_type=sa.dialects.postgresql.JSONB(), nullable=True)
    # The id of a PDF uploaded to WhatsApp's media store, kept only until it is deleted there (then NULL).
    op.add_column('result_deliveries', sa.Column('provider_media_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('result_deliveries', 'provider_media_id')
    # Only possible while every report still has content (rows created after the upgrade have none).
    op.alter_column('reports', 'content', existing_type=sa.dialects.postgresql.JSONB(), nullable=False)
