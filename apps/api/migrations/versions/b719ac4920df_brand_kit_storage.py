"""Persist the existing brand-kit model."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b719ac4920df"
down_revision = "68fe9c8a63bf"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "brand_kits",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "config", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("logo_key", sa.String(length=1024), nullable=True),
        sa.Column("logo_size", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brand_kits_user_id", "brand_kits", ["user_id"])


def downgrade():
    op.drop_index("ix_brand_kits_user_id", table_name="brand_kits")
    op.drop_table("brand_kits")
