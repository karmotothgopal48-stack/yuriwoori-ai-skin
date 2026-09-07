from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2bdb59abfec"
down_revision: Union[str, Sequence[str], None] = "bc6802b2d24e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "chips",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "benefits_raw",
            sa.String(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "benefits_raw")
    op.drop_column("products", "chips")
