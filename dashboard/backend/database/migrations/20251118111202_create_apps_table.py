"""Create apps table"""

from alembic import op
import sqlalchemy as sa


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
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uix_project_app"),
    )
    op.create_index(op.f("ix_apps_id"), "apps", ["id"], unique=False)
    op.create_index(op.f("ix_apps_name"), "apps", ["name"], unique=False)


def downgrade():
    """Drop apps table."""
    op.drop_table("apps")
