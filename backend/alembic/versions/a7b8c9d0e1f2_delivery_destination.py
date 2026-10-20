"""bind each report delivery to the contact it was made for (additive; backfills existing rows)

Revision ID: a7b8c9d0e1f2
Revises: f2c3d4e5a6b7
Create Date: 2026-10-15 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f2c3d4e5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The email / WhatsApp number the report may be sent to: the owner's contact when the report was made.
    op.add_column('result_deliveries', sa.Column('destination', sa.String(), nullable=True))
    # Existing rows: the owner's current contact (the best record there is). No row is removed or re-sent.
    op.execute("""
        UPDATE result_deliveries AS rd
        SET destination = CASE WHEN rd.channel = 'email' THEN u.email ELSE u.whatsapp END
        FROM users AS u
        WHERE u.id = rd.user_id AND rd.destination IS NULL
    """)


def downgrade() -> None:
    op.drop_column('result_deliveries', 'destination')
