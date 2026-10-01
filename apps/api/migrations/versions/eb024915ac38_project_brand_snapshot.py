"""Keep project branding stable when a reusable kit changes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "eb024915ac38"
down_revision = "b719ac4920df"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column(
            "brand_config",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("projects", "brand_config", server_default=None)


def downgrade():
    op.drop_column("projects", "brand_config")
