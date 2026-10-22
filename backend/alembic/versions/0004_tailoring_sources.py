"""Immutable tailoring source bundles and separate activation history."""
from alembic import op
import sqlalchemy as sa

revision = "0004_tailoring_sources"
down_revision = "0003_attribution"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "tailoring_source_versions" not in existing:
        op.create_table("tailoring_source_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("profile_id", sa.String(36), sa.ForeignKey("resume_profiles.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("bank_version", sa.String(128), nullable=False),
            sa.Column("bundle_hash", sa.String(64), nullable=False),
            *[sa.Column(name, sa.Text(), nullable=False) for name in ("bank_markdown", "preferences_yaml", "template_tex", "style_guide")],
            *[sa.Column(name, sa.JSON(), nullable=False) for name in ("bank", "preferences", "projection", "validation", "hashes")],
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("profile_id", "bundle_hash", name="uq_tailoring_source_bundle"))
        op.create_index("ix_tailoring_source_versions_profile_id", "tailoring_source_versions", ["profile_id"])
    if "tailoring_source_events" not in existing:
        op.create_table("tailoring_source_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source_id", sa.String(36), sa.ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("source_id", "sequence", name="uq_tailoring_source_event"))
        op.create_index("ix_tailoring_source_events_source_id", "tailoring_source_events", ["source_id"])
    if "tailoring_profile_states" not in existing:
        op.create_table("tailoring_profile_states",
            sa.Column("profile_id", sa.String(36), sa.ForeignKey("resume_profiles.id", ondelete="RESTRICT"), primary_key=True),
            sa.Column("active_source_id", sa.String(36), sa.ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT")),
            sa.Column("revision", sa.Integer(), nullable=False))
    if op.get_bind().dialect.name == "sqlite":
        for table in ("tailoring_source_versions", "tailoring_source_events"):
            op.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_immutable BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'Tailoring history is immutable'); END")


def downgrade():
    for table in ("tailoring_profile_states", "tailoring_source_events", "tailoring_source_versions"):
        op.drop_table(table)
