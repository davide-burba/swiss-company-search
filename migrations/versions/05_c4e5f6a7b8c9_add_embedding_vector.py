"""Add embedding vector column for semantic search

Revision ID: c4e5f6a7b8c9
Revises: a3f8c2d91b47
Create Date: 2026-03-08 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "a3f8c2d91b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add embedding column (384 dims — matches all-MiniLM-L6-v2)
    op.add_column(
        "zefix_companies",
        sa.Column(
            "embedding",
            sa.Text,  # placeholder; replaced below with raw DDL
            nullable=True,
        ),
    )
    # Swap the column to the real vector type after adding it
    op.execute(
        f"ALTER TABLE zefix_companies ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) USING NULL"
    )

    # HNSW index for fast approximate nearest-neighbour cosine search
    op.execute(
        "CREATE INDEX idx_zefix_companies_embedding "
        "ON zefix_companies USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_zefix_companies_embedding")
    op.drop_column("zefix_companies", "embedding")
