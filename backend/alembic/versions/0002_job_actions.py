"""Add one next action per application."""
from alembic import op
import sqlalchemy as sa

revision = "0002_job_actions"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Also supports databases created using metadata before adopting Alembic.
    if "job_actions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "job_actions",
            sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_job_actions_due_date", "job_actions", ["due_date"])


def downgrade():
    op.drop_table("job_actions")
