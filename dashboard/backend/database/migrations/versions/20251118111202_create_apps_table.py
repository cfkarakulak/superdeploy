"""Create apps table

Revision ID: 20251118111202
Revises: 20251118111201
Create Date: 2025-11-18 11:12:02

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111202"
down_revision = "20251118111201"
branch_labels = None
depends_on = None


def upgrade():
    """Create apps table."""
    op.create_table(
        "apps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("repo", sa.String(length=255), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("vm", sa.String(length=50), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("external_port", sa.Integer(), nullable=True),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("replicas", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("services", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uix_project_app"),
    )
    op.create_index(op.f("ix_apps_id"), "apps", ["id"], unique=False)
    op.create_index(op.f("ix_apps_name"), "apps", ["name"], unique=False)
    op.create_index(op.f("ix_apps_project_id"), "apps", ["project_id"], unique=False)


def downgrade():
    """Drop apps table."""
    op.drop_table("apps")
