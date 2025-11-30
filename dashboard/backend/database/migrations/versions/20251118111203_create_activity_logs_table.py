"""Create activity_logs table

Revision ID: 20251118111203
Revises: 20251118111202
Create Date: 2025-11-18 11:12:03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111203"
down_revision = "20251118111202"
branch_labels = None
depends_on = None


def upgrade():
    """Create activity_logs table."""
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_logs_project_name"),
        "activity_logs",
        ["project_name"],
        unique=False,
    )


def downgrade():
    """Drop activity_logs table."""
    op.drop_table("activity_logs")
