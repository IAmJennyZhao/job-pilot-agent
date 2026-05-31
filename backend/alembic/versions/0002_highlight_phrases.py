"""add highlight phrases

Revision ID: 0002_highlight_phrases
Revises: 0001_initial
Create Date: 2026-05-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_highlight_phrases"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("company_research_snapshots", "highlight_phrases"):
        op.add_column(
            "company_research_snapshots",
            sa.Column("highlight_phrases", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )
    if not _has_column("advanced_job_analyses", "highlight_phrases"):
        op.add_column(
            "advanced_job_analyses",
            sa.Column("highlight_phrases", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )


def downgrade() -> None:
    if _has_column("advanced_job_analyses", "highlight_phrases"):
        op.drop_column("advanced_job_analyses", "highlight_phrases")
    if _has_column("company_research_snapshots", "highlight_phrases"):
        op.drop_column("company_research_snapshots", "highlight_phrases")
