"""add interview practice inventory

Revision ID: 0004_interview_practice
Revises: 0003_profile_assets
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_interview_practice"
down_revision: str | None = "0003_profile_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_column("interview_sessions", "job_id"):
        with op.batch_alter_table("interview_sessions") as batch_op:
            batch_op.alter_column("job_id", existing_type=sa.String(length=36), nullable=True)

    if not _has_column("interview_sessions", "target_category"):
        op.add_column("interview_sessions", sa.Column("target_category", sa.String(length=64), nullable=True))
        op.create_index("ix_interview_sessions_target_category", "interview_sessions", ["target_category"])
    if not _has_column("interview_sessions", "target_role"):
        op.add_column("interview_sessions", sa.Column("target_role", sa.String(length=255), nullable=True))
    if not _has_column("interview_sessions", "stage"):
        op.add_column(
            "interview_sessions",
            sa.Column("stage", sa.String(length=64), nullable=False, server_default="mixed"),
        )
        op.create_index("ix_interview_sessions_stage", "interview_sessions", ["stage"])
    if not _has_column("interview_sessions", "question_type"):
        op.add_column(
            "interview_sessions",
            sa.Column("question_type", sa.String(length=100), nullable=False, server_default="mixed"),
        )
        op.create_index("ix_interview_sessions_question_type", "interview_sessions", ["question_type"])

    if not _has_table("interview_questions"):
        op.create_table(
            "interview_questions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("job_id", sa.String(length=36), nullable=True),
            sa.Column("resume_profile_id", sa.String(length=36), nullable=True),
            sa.Column("target_category", sa.String(length=64), nullable=True),
            sa.Column("target_role", sa.String(length=255), nullable=True),
            sa.Column("stage", sa.String(length=64), nullable=False),
            sa.Column("question_type", sa.String(length=100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("why_it_matters", sa.Text(), nullable=True),
            sa.Column("strong_answer_should_include", sa.JSON(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("prompt_metadata", sa.JSON(), nullable=False),
            sa.Column("weak_point_tags", sa.JSON(), nullable=False),
            sa.Column("asked_count", sa.Integer(), nullable=False),
            sa.Column("last_asked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["resume_profile_id"], ["resume_profiles.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_interview_questions_job_id", "interview_questions", ["job_id"])
        op.create_index("ix_interview_questions_resume_profile_id", "interview_questions", ["resume_profile_id"])
        op.create_index("ix_interview_questions_target_category", "interview_questions", ["target_category"])
        op.create_index("ix_interview_questions_stage", "interview_questions", ["stage"])
        op.create_index("ix_interview_questions_question_type", "interview_questions", ["question_type"])
        op.create_index("ix_interview_questions_source", "interview_questions", ["source"])
        op.create_index("ix_interview_questions_last_asked_at", "interview_questions", ["last_asked_at"])

    if not _has_column("interview_messages", "question_id"):
        op.add_column("interview_messages", sa.Column("question_id", sa.String(length=36), nullable=True))
        op.create_index("ix_interview_messages_question_id", "interview_messages", ["question_id"])
        if op.get_bind().dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_interview_messages_question_id",
                "interview_messages",
                "interview_questions",
                ["question_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    if _has_column("interview_messages", "question_id"):
        op.drop_index("ix_interview_messages_question_id", table_name="interview_messages")
        op.drop_column("interview_messages", "question_id")
    if _has_table("interview_questions"):
        op.drop_table("interview_questions")
    if _has_column("interview_sessions", "question_type"):
        op.drop_index("ix_interview_sessions_question_type", table_name="interview_sessions")
        op.drop_column("interview_sessions", "question_type")
    if _has_column("interview_sessions", "stage"):
        op.drop_index("ix_interview_sessions_stage", table_name="interview_sessions")
        op.drop_column("interview_sessions", "stage")
    if _has_column("interview_sessions", "target_role"):
        op.drop_column("interview_sessions", "target_role")
    if _has_column("interview_sessions", "target_category"):
        op.drop_index("ix_interview_sessions_target_category", table_name="interview_sessions")
        op.drop_column("interview_sessions", "target_category")
