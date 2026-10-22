"""Evidence-backed intake decisions and retry-safe saving."""
from alembic import op
import sqlalchemy as sa

revision = "0005_job_intake"
down_revision = "0004_tailoring_sources"
branch_labels = None
depends_on = None


def upgrade():
    if "job_intake_reviews" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("job_intake_reviews",
            sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("request_key", sa.String(128), nullable=False, unique=True),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("review", sa.JSON(), nullable=False),
            sa.Column("evaluation", sa.JSON(), nullable=False),
            sa.Column("preference_snapshot", sa.JSON(), nullable=True),
            sa.Column("source_id", sa.String(36), sa.ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT")),
            sa.Column("decision", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("job_intake_reviews")
