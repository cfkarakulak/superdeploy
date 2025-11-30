"""Create processes table

Revision ID: 20251121194643
Revises: 20251118111209
Create Date: 2025-11-21 19:46:43

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251121194643"
down_revision = "20251118111209"
branch_labels = None
depends_on = None


def upgrade():
    """Create processes table."""
    op.create_table(
        "processes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("replicas", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_id", "name", name="uix_process_app"),
    )
    op.create_index(op.f("idx_processes_app_id"), "processes", ["app_id"], unique=False)


def downgrade():
    """Drop processes table."""
    op.drop_table("processes")
