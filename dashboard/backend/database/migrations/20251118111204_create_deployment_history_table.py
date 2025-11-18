"""Create deployment_history table"""

from alembic import op
import sqlalchemy as sa


revision = "20251118111204"
down_revision = "20251118111203"
branch_labels = None
depends_on = None


def upgrade():
    """Create deployment_history table."""
    op.create_table(
        "deployment_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("app_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("git_sha", sa.String(length=100), nullable=True),
        sa.Column("branch", sa.String(length=100), nullable=True),
        sa.Column("deployed_at", sa.DateTime(), nullable=True),
        sa.Column("deployed_by", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_deployment_history_id"), "deployment_history", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_deployment_history_app_name"),
        "deployment_history",
        ["app_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployment_history_deployed_at"),
        "deployment_history",
        ["deployed_at"],
        unique=False,
    )


def downgrade():
    """Drop deployment_history table."""
    op.drop_table("deployment_history")
