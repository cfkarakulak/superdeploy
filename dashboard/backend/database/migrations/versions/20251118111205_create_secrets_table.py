"""Create secrets table

Revision ID: 20251118111205
Revises: 20251118111204
Create Date: 2025-11-18 11:12:05

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111205"
down_revision = "20251118111204"
branch_labels = None
depends_on = None


def upgrade():
    """Create secrets table with proper FK relationships."""
    op.create_table(
        "secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "app_id", sa.Integer(), nullable=True
        ),  # NULL = shared/project-level secret
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "environment",
            sa.String(length=50),
            nullable=False,
            server_default="production",
        ),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="app"),
        sa.Column("editable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "app_id", "key", "environment", name="uix_secret"
        ),
    )
    op.create_index(op.f("ix_secrets_id"), "secrets", ["id"], unique=False)
    op.create_index(
        op.f("ix_secrets_project_id"), "secrets", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_secrets_app_id"), "secrets", ["app_id"], unique=False)


def downgrade():
    """Drop secrets table."""
    op.drop_index(op.f("ix_secrets_app_id"), table_name="secrets")
    op.drop_index(op.f("ix_secrets_project_id"), table_name="secrets")
    op.drop_index(op.f("ix_secrets_id"), table_name="secrets")
    op.drop_table("secrets")
