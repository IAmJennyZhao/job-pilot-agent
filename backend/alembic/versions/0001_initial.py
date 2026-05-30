"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("role_title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("remote_type", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("responsibilities", sa.JSON(), nullable=False),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("pay_min", sa.Integer(), nullable=True),
        sa.Column("pay_max", sa.Integer(), nullable=True),
        sa.Column("pay_currency", sa.String(length=16), nullable=True),
        sa.Column("pay_period", sa.String(length=64), nullable=True),
        sa.Column("pay_raw", sa.Text(), nullable=True),
        sa.Column("pay_annual_min", sa.Integer(), nullable=True),
        sa.Column("pay_annual_max", sa.Integer(), nullable=True),
        sa.Column("pay_conversion_note", sa.Text(), nullable=True),
        sa.Column("benefits", sa.JSON(), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("extraction_confidence", sa.Integer(), nullable=True),
        sa.Column("extraction_warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_company", "jobs", ["company"])
    op.create_index("ix_jobs_role_title", "jobs", ["role_title"])
    op.create_index("ix_jobs_category", "jobs", ["category"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_links_job_id", "job_links", ["job_id"])
    op.create_index("ix_job_links_kind", "job_links", ["kind"])
    op.create_index("ix_job_links_url", "job_links", ["url"])

    op.create_table(
        "job_status_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_status_events_job_id", "job_status_events", ["job_id"])
    op.create_index("ix_job_status_events_to_status", "job_status_events", ["to_status"])
    op.create_index("ix_job_status_events_changed_at", "job_status_events", ["changed_at"])

    op.create_table(
        "company_research_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_company_name", sa.String(length=255), nullable=False),
        sa.Column("sentiment", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("themes", sa.JSON(), nullable=False),
        sa.Column("source_links", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("coverage_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_company_name"),
    )
    op.create_index("ix_company_research_snapshots_normalized_company_name", "company_research_snapshots", ["normalized_company_name"])

    op.create_table(
        "advanced_job_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("company_research_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("job_insights", sa.JSON(), nullable=True),
        sa.Column("company_sentiment", sa.JSON(), nullable=True),
        sa.Column("top_company_fit", sa.JSON(), nullable=False),
        sa.Column("resume_keywords", sa.JSON(), nullable=False),
        sa.Column("risks_gaps", sa.JSON(), nullable=False),
        sa.Column("expected_questions", sa.JSON(), nullable=False),
        sa.Column("source_links", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_research_id"], ["company_research_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_advanced_job_analyses_job_id", "advanced_job_analyses", ["job_id"])
    op.create_index("ix_advanced_job_analyses_company_research_id", "advanced_job_analyses", ["company_research_id"])

    op.create_table(
        "resume_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("projects", sa.JSON(), nullable=False),
        sa.Column("experience", sa.JSON(), nullable=False),
        sa.Column("education", sa.JSON(), nullable=False),
        sa.Column("certifications", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_profiles_is_active", "resume_profiles", ["is_active"])

    op.create_table(
        "job_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("responsibilities", sa.JSON(), nullable=False),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("preferred_skills", sa.JSON(), nullable=False),
        sa.Column("technologies", sa.JSON(), nullable=False),
        sa.Column("resume_keywords", sa.JSON(), nullable=False),
        sa.Column("interview_topics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_job_analyses_job_id", "job_analyses", ["job_id"])

    op.create_table(
        "resume_suggestions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("resume_profile_id", sa.String(length=36), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("weak_skills", sa.JSON(), nullable=False),
        sa.Column("keyword_suggestions", sa.JSON(), nullable=False),
        sa.Column("bullet_suggestions", sa.JSON(), nullable=False),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_suggestions_job_id", "resume_suggestions", ["job_id"])
    op.create_index("ix_resume_suggestions_resume_profile_id", "resume_suggestions", ["resume_profile_id"])

    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("resume_profile_id", sa.String(length=36), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sessions_job_id", "interview_sessions", ["job_id"])
    op.create_index("ix_interview_sessions_resume_profile_id", "interview_sessions", ["resume_profile_id"])

    op.create_table(
        "skill_gaps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resume_profile_id", sa.String(length=36), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("user_level", sa.String(length=32), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skill_gaps_resume_profile_id", "skill_gaps", ["resume_profile_id"])
    op.create_index("ix_skill_gaps_skill_name", "skill_gaps", ["skill_name"])
    op.create_index("ix_skill_gaps_source", "skill_gaps", ["source"])

    op.create_table(
        "interview_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=100), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_messages_session_id", "interview_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("interview_messages")
    op.drop_table("skill_gaps")
    op.drop_table("interview_sessions")
    op.drop_table("resume_suggestions")
    op.drop_table("job_analyses")
    op.drop_table("advanced_job_analyses")
    op.drop_table("company_research_snapshots")
    op.drop_table("job_status_events")
    op.drop_table("job_links")
    op.drop_table("resume_profiles")
    op.drop_table("jobs")

