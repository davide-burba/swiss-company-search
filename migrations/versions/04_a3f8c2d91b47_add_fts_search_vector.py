"""Add FTS search_vector column with GIN index and trigger

Revision ID: a3f8c2d91b47
Revises: 631e4ef94cee
Create Date: 2026-03-06 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "a3f8c2d91b47"
down_revision: Union[str, Sequence[str], None] = "631e4ef94cee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the tsvector column
    op.add_column(
        "zefix_companies",
        sa.Column("search_vector", TSVECTOR, nullable=True),
    )

    # Create GIN index for fast FTS lookups
    op.create_index(
        "idx_zefix_companies_search_vector",
        "zefix_companies",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Populate existing rows.
    # Both fields use 'simple' (no stemming) so that prefix matching with :*
    # works uniformly across names and descriptions.
    op.execute("""
        UPDATE zefix_companies
        SET search_vector =
            setweight(to_tsvector('simple', coalesce(legal_name, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(description_en, '')), 'B')
    """)

    # Trigger function to keep search_vector up to date
    op.execute("""
        CREATE OR REPLACE FUNCTION zefix_companies_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.legal_name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.description_en, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER zefix_companies_search_vector_trigger
        BEFORE INSERT OR UPDATE OF legal_name, description_en
        ON zefix_companies
        FOR EACH ROW EXECUTE FUNCTION zefix_companies_search_vector_update();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS zefix_companies_search_vector_trigger ON zefix_companies"
    )
    op.execute("DROP FUNCTION IF EXISTS zefix_companies_search_vector_update")
    op.drop_index("idx_zefix_companies_search_vector", table_name="zefix_companies")
    op.drop_column("zefix_companies", "search_vector")
