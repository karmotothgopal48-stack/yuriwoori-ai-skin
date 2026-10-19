"""skin-analysis reports, delivery tracking and report-sending consent (additive only)

Revision ID: f2c3d4e5a6b7
Revises: e1b2c3d4f5a6
Create Date: 2026-10-13 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f2c3d4e5a6b7'
down_revision: Union[str, Sequence[str], None] = 'e1b2c3d4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # When the user agreed to have their report sent to their email / WhatsApp (null = not agreed)
    op.add_column('users', sa.Column('report_consent_at', sa.DateTime(), nullable=True))

    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scans.id'), nullable=False, unique=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('content', postgresql.JSONB(), nullable=False),  # the report as generated (saved results + live store data)
        sa.Column('token_hash', sa.String(), nullable=False, unique=True),  # SHA-256 of the link token, never the token
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('last_viewed_at', sa.DateTime(), nullable=True),
    )

    # Delivery tracking on the existing table (it has no rows yet; new columns are nullable / defaulted)
    op.add_column('result_deliveries', sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('reports.id'), nullable=True))
    op.add_column('result_deliveries', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('result_deliveries', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('result_deliveries', sa.Column('sent_at', sa.DateTime(), nullable=True))
    # one delivery per report and channel: retries update it instead of creating duplicates
    op.create_index('uq_result_deliveries_report_channel', 'result_deliveries', ['report_id', 'channel'], unique=True,
                    postgresql_where=sa.text('report_id IS NOT NULL'))
    op.create_index('ix_result_deliveries_provider_message_id', 'result_deliveries', ['provider_message_id'])


def downgrade() -> None:
    op.drop_index('ix_result_deliveries_provider_message_id', table_name='result_deliveries')
    op.drop_index('uq_result_deliveries_report_channel', table_name='result_deliveries')
    op.drop_column('result_deliveries', 'sent_at')
    op.drop_column('result_deliveries', 'updated_at')
    op.drop_column('result_deliveries', 'attempts')
    op.drop_column('result_deliveries', 'report_id')
    op.drop_table('reports')
    op.drop_column('users', 'report_consent_at')
