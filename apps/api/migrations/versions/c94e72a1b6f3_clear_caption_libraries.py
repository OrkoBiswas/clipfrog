"""Clear saved caption templates while removing the bundled catalog."""

from alembic import op

revision = "c94e72a1b6f3"
down_revision = "fa198ac32d70"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM caption_libraries")


def downgrade():
    """Saved custom templates cannot be restored after this cleanup."""