"""Add sector columns to zefix table

Revision ID: 591ec5b4402d
Revises: 7200d5b261e8
Create Date: 2026-03-06 18:37:20.394387

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "591ec5b4402d"
down_revision: Union[str, Sequence[str], None] = "7200d5b261e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "zefix_companies",
        sa.Column("sector_section", sa.String(length=1), nullable=True),
    )
    op.add_column(
        "zefix_companies",
        sa.Column("sector_division", sa.String(length=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("zefix_companies", "sector_division")
    op.drop_column("zefix_companies", "sector_section")
