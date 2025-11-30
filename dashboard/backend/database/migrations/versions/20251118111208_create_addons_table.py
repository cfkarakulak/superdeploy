"""Create addons table

Revision ID: 20251118111208
Revises: 20251118111207
Create Date: 2025-11-18 11:12:08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111208"
down_revision = "20251118111207"
branch_labels = None
depends_on = None


def upgrade():
    """Create addons table."""
    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("instance_name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("vm", sa.String(length=50), nullable=False, server_default="core"),
        sa.Column("plan", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "category", "instance_name", name="uix_project_addon"),
    )
    op.create_index(op.f("ix_addons_id"), "addons", ["id"], unique=False)
    op.create_index(
        op.f("ix_addons_project_id"), "addons", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_addons_category"), "addons", ["category"], unique=False)


def downgrade():
    """Drop addons table."""
    op.drop_table("addons")
