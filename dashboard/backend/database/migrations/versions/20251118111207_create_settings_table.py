"""Create settings table

Revision ID: 20251118111207
Revises: 20251118111206
Create Date: 2025-11-18 11:12:07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111207"
down_revision = "20251118111206"
branch_labels = None
depends_on = None


def upgrade():
    """Create settings table."""
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_settings_id"), "settings", ["id"], unique=False)
    op.create_index(op.f("ix_settings_key"), "settings", ["key"], unique=True)


def downgrade():
    """Drop settings table."""
    op.drop_table("settings")
