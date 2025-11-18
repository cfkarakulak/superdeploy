"""Create activity_logs table"""

from alembic import op
import sqlalchemy as sa


revision = "20251118111203"
down_revision = "20251118111202"
branch_labels = None
depends_on = None


def upgrade():
    """Create activity_logs table."""
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("app_name", sa.String(length=100), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_id"), "activity_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_activity_logs_type"), "activity_logs", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_activity_logs_app_name"), "activity_logs", ["app_name"], unique=False
    )
    op.create_index(
        op.f("ix_activity_logs_timestamp"), "activity_logs", ["timestamp"], unique=False
    )


def downgrade():
    """Drop activity_logs table."""
    op.drop_table("activity_logs")
