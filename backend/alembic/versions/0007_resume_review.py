"""Immutable manual resume revisions and exact-version approvals."""
from alembic import op
import sqlalchemy as sa

revision = "0007_resume_review"
down_revision = "0006_resume_generation"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "resume_edit_revisions" not in existing:
        op.create_table("resume_edit_revisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("baseline_id", sa.String(36), sa.ForeignKey("tailored_revisions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("parent_id", sa.String(36), sa.ForeignKey("resume_edit_revisions.id", ondelete="RESTRICT")),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("origin", sa.String(16), nullable=False),
            sa.Column("restored_from_id", sa.String(36)),
            sa.Column("request_key", sa.String(128), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("plain_text", sa.Text(), nullable=False),
            sa.Column("validation", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("baseline_id", "sequence", name="uq_resume_edit_sequence"),
            sa.UniqueConstraint("baseline_id", "request_key", name="uq_resume_edit_request"))
    if "resume_review_approvals" not in existing:
        op.create_table("resume_review_approvals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("baseline_id", sa.String(36), sa.ForeignKey("tailored_revisions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("edit_revision_id", sa.String(36), sa.ForeignKey("resume_edit_revisions.id", ondelete="RESTRICT")),
            sa.Column("revision_id", sa.String(36), nullable=False, unique=True),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("validation_hash", sa.String(64), nullable=False),
            sa.Column("validator_version", sa.String(64), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if op.get_bind().dialect.name == "sqlite":
        for name in ("resume_edit_revisions", "resume_review_approvals"):
            op.execute(f"CREATE TRIGGER IF NOT EXISTS {name}_immutable BEFORE UPDATE ON {name} BEGIN SELECT RAISE(ABORT, 'Resume history is immutable'); END")


def downgrade():
    op.drop_table("resume_review_approvals")
    op.drop_table("resume_edit_revisions")
