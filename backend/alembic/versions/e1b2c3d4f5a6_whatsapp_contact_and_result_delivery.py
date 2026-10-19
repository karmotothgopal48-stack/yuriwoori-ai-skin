"""whatsapp contact, contact verification and result delivery records (additive only)

Revision ID: e1b2c3d4f5a6
Revises: d3a1f0c2b7e4
Create Date: 2026-10-13 17:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e1b2c3d4f5a6'
down_revision: Union[str, Sequence[str], None] = 'd3a1f0c2b7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable columns only: existing users keep working and simply have no WhatsApp number yet.
    op.add_column('users', sa.Column('whatsapp', sa.String(), nullable=True))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('whatsapp_verified_at', sa.DateTime(), nullable=True))

    op.create_table(
        'contact_verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('channel', sa.String(), nullable=False),  # "email" | "whatsapp"
        sa.Column('destination', sa.String(), nullable=False),  # the address/number the code was sent to
        sa.Column('code_hash', sa.String(), nullable=False),  # HMAC of the code, never the code
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'result_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scans.id'), nullable=False, index=True),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),  # "accepted" (by the provider) | "failed"
        sa.Column('provider_message_id', sa.String(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('result_deliveries')
    op.drop_table('contact_verifications')
    op.drop_column('users', 'whatsapp_verified_at')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'whatsapp')
