"""Freeze source, role category and resume version for outcome reporting."""
from alembic import op
import sqlalchemy as sa

revision = "0003_attribution"
down_revision = "0002_job_actions"
branch_labels = None
depends_on = None


def upgrade():
    if "application_attributions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("application_attributions",
            sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("source", sa.String(255), nullable=False),
            sa.Column("category", sa.String(255), nullable=False),
            sa.Column("resume_version", sa.String(500), nullable=False))


def downgrade():
    op.drop_table("application_attributions")
