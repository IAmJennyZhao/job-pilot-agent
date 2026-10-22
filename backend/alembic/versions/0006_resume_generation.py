"""Persistent resume runs, stage attempts and immutable revisions."""
from alembic import op
import sqlalchemy as sa

revision = "0006_resume_generation"
down_revision = "0005_job_intake"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "tailoring_runs" not in existing:
        op.create_table("tailoring_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("profile_id", sa.String(36), sa.ForeignKey("resume_profiles.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("source_id", sa.String(36), sa.ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("parent_run_id", sa.String(36), sa.ForeignKey("tailoring_runs.id", ondelete="RESTRICT")),
            sa.Column("request_key", sa.String(128), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("state", sa.String(32), nullable=False),
            sa.Column("active_key", sa.String(128), unique=True),
            sa.Column("error", sa.String(500)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("profile_id", "job_id", "request_key", name="uq_tailoring_request"))
    if "tailoring_stage_attempts" not in existing:
        op.create_table("tailoring_stage_attempts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("tailoring_runs.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("stage", sa.String(16), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(32), nullable=False), sa.Column("input_data", sa.JSON(), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("output_data", sa.JSON()),
            sa.Column("output_hash", sa.String(64)), sa.Column("validation", sa.JSON()),
            sa.Column("provider_metadata", sa.JSON(), nullable=False), sa.Column("prompt_version", sa.String(64), nullable=False),
            sa.Column("error", sa.String(500)),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("run_id", "stage", "attempt", name="uq_tailoring_attempt"))
    if "tailored_revisions" not in existing:
        op.create_table("tailored_revisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("tailoring_runs.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("content", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("plain_text", sa.Text(), nullable=False), sa.Column("validation", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if op.get_bind().dialect.name == "sqlite":
        op.execute("CREATE TRIGGER IF NOT EXISTS tailored_revision_immutable BEFORE UPDATE ON tailored_revisions BEGIN SELECT RAISE(ABORT, 'Generated revisions are immutable'); END")


def downgrade():
    for table in ("tailored_revisions", "tailoring_stage_attempts", "tailoring_runs"):
        op.drop_table(table)
