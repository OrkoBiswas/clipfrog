"""Local highlight scoring metadata and explicit user feedback."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e482a03c6d19"
down_revision = "c94e72a1b6f3"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column(
        "clip_candidates",
        sa.Column("scoring_metadata", json_type, nullable=False, server_default="{}"),
    )
    op.alter_column("clip_candidates", "scoring_metadata", server_default=None)
    op.create_table(
        "highlight_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("features", json_type, nullable=False),
        sa.Column("engine_version", sa.String(50), nullable=False),
        sa.UniqueConstraint("user_id", "project_id", "fingerprint"),
    )
    op.create_index("ix_highlight_feedback_user_id", "highlight_feedback", ["user_id"])
    op.create_index("ix_highlight_feedback_project_id", "highlight_feedback", ["project_id"])


def downgrade():
    op.drop_table("highlight_feedback")
    op.drop_column("clip_candidates", "scoring_metadata")
