"""Caption libraries and isolated short preview clips."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "fa198ac32d70"
down_revision = "eb024915ac38"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clips", sa.Column("is_preview", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column("clips", "is_preview", server_default=None)
    op.create_table(
        "caption_libraries",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("data", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("caption_libraries")
    op.drop_column("clips", "is_preview")
