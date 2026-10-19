"""customer follow-up workbook: one sync-state row per customer (additive; no existing row is changed)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-19 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing customers are not queued here: exporting them is an explicit step (scripts/customer_sheet.py reconcile).
    op.create_table(
        'customer_sheet_sync',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('wanted_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('claimed_version', sa.Integer(), nullable=True),
        sa.Column('synced_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_customer_sheet_sync_status', 'customer_sheet_sync', ['status'])


def downgrade() -> None:
    op.drop_index('ix_customer_sheet_sync_status', table_name='customer_sheet_sync')
    op.drop_table('customer_sheet_sync')
