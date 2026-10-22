"""Immutable render bundles, preview receipts and exact-artifact approvals."""
from alembic import op
import sqlalchemy as sa

revision = "0008_resume_exports"
down_revision = "0007_resume_review"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "resume_renders" not in existing:
        op.create_table("resume_renders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("baseline_id", sa.String(36), sa.ForeignKey("tailored_revisions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("edit_revision_id", sa.String(36), sa.ForeignKey("resume_edit_revisions.id", ondelete="RESTRICT")),
            sa.Column("revision_id", sa.String(36), nullable=False),
            *[sa.Column(name, sa.String(64), nullable=False) for name in ("content_hash", "validation_hash", "input_hash", "manifest_hash")],
            sa.Column("render_key", sa.String(64), nullable=False, unique=True),
            sa.Column("bundle", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if "resume_preview_receipts" not in existing:
        op.create_table("resume_preview_receipts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("render_id", sa.String(36), sa.ForeignKey("resume_renders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("manifest_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if "resume_export_approvals" not in existing:
        op.create_table("resume_export_approvals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("render_id", sa.String(36), sa.ForeignKey("resume_renders.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("content_approval_id", sa.String(36), sa.ForeignKey("resume_review_approvals.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("preview_receipt_id", sa.String(36), sa.ForeignKey("resume_preview_receipts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("manifest_hash", sa.String(64), nullable=False),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if op.get_bind().dialect.name == "sqlite":
        for name in ("resume_renders", "resume_preview_receipts", "resume_export_approvals"):
            op.execute(f"CREATE TRIGGER IF NOT EXISTS {name}_immutable BEFORE UPDATE ON {name} BEGIN SELECT RAISE(ABORT, 'Resume artifacts are immutable'); END")


def downgrade():
    for name in ("resume_export_approvals", "resume_preview_receipts", "resume_renders"):
        op.drop_table(name)
