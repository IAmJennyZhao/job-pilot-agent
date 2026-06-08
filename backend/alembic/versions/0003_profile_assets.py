"""add profile assets

Revision ID: 0003_profile_assets
Revises: 0002_highlight_phrases
Create Date: 2026-06-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_profile_assets"
down_revision: str | None = "0002_highlight_phrases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column("resume_profiles", "skill_groups"):
        op.add_column(
            "resume_profiles",
            sa.Column("skill_groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )

    if not _has_table("resume_options"):
        op.create_table(
            "resume_options",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("resume_profile_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("candidate_name", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("source_filename", sa.String(length=255), nullable=True),
            sa.Column("file_path", sa.String(length=1024), nullable=True),
            sa.Column("content_type", sa.String(length=128), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("parsed_text", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("target_roles", sa.JSON(), nullable=False),
            sa.Column("target_keywords", sa.JSON(), nullable=False),
            sa.Column("skills", sa.JSON(), nullable=False),
            sa.Column("skill_groups", sa.JSON(), nullable=False),
            sa.Column("projects", sa.JSON(), nullable=False),
            sa.Column("experience", sa.JSON(), nullable=False),
            sa.Column("education", sa.JSON(), nullable=False),
            sa.Column("certifications", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_resume_options_resume_profile_id", "resume_options", ["resume_profile_id"])
        op.create_index("ix_resume_options_status", "resume_options", ["status"])

    if not _has_table("cover_letter_templates"):
        op.create_table(
            "cover_letter_templates",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("resume_profile_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("target_roles", sa.JSON(), nullable=False),
            sa.Column("target_keywords", sa.JSON(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_cover_letter_templates_resume_profile_id",
            "cover_letter_templates",
            ["resume_profile_id"],
        )

    if not _has_column("jobs", "selected_resume_option_id"):
        op.add_column("jobs", sa.Column("selected_resume_option_id", sa.String(length=36), nullable=True))
        op.create_index("ix_jobs_selected_resume_option_id", "jobs", ["selected_resume_option_id"])
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_jobs_selected_resume_option_id",
                "jobs",
                "resume_options",
                ["selected_resume_option_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _has_column("jobs", "selected_cover_letter_template_id"):
        op.add_column("jobs", sa.Column("selected_cover_letter_template_id", sa.String(length=36), nullable=True))
        op.create_index(
            "ix_jobs_selected_cover_letter_template_id",
            "jobs",
            ["selected_cover_letter_template_id"],
        )
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_jobs_selected_cover_letter_template_id",
                "jobs",
                "cover_letter_templates",
                ["selected_cover_letter_template_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _has_table("asset_recommendation_snapshots"):
        op.create_table(
            "asset_recommendation_snapshots",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("job_id", sa.String(length=36), nullable=False),
            sa.Column("source", sa.String(length=16), nullable=False),
            sa.Column("resume_rankings", sa.JSON(), nullable=False),
            sa.Column("cover_letter_rankings", sa.JSON(), nullable=False),
            sa.Column("errors", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_asset_recommendation_snapshots_job_id",
            "asset_recommendation_snapshots",
            ["job_id"],
        )
        op.create_index(
            "ix_asset_recommendation_snapshots_source",
            "asset_recommendation_snapshots",
            ["source"],
        )


def downgrade() -> None:
    if _has_table("asset_recommendation_snapshots"):
        op.drop_table("asset_recommendation_snapshots")
    if _has_column("jobs", "selected_cover_letter_template_id"):
        op.drop_column("jobs", "selected_cover_letter_template_id")
    if _has_column("jobs", "selected_resume_option_id"):
        op.drop_column("jobs", "selected_resume_option_id")
    if _has_table("cover_letter_templates"):
        op.drop_table("cover_letter_templates")
    if _has_table("resume_options"):
        op.drop_table("resume_options")
    if _has_column("resume_profiles", "skill_groups"):
        op.drop_column("resume_profiles", "skill_groups")
