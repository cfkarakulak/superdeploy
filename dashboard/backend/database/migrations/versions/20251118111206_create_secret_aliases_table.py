"""Create secret_aliases table

Revision ID: 20251118111206
Revises: 20251118111205
Create Date: 2025-11-18 11:12:06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111206"
down_revision = "20251118111205"
branch_labels = None
depends_on = None


def upgrade():
    """Create secret_aliases table with proper FK relationships."""
    op.create_table(
        "secret_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("alias_key", sa.String(length=255), nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "app_id", "alias_key", name="uix_secret_alias"
        ),
    )
    op.create_index(
        op.f("ix_secret_aliases_id"), "secret_aliases", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_secret_aliases_project_id"),
        "secret_aliases",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_secret_aliases_app_id"), "secret_aliases", ["app_id"], unique=False
    )


def downgrade():
    """Drop secret_aliases table."""
    op.drop_index(op.f("ix_secret_aliases_app_id"), table_name="secret_aliases")
    op.drop_index(op.f("ix_secret_aliases_project_id"), table_name="secret_aliases")
    op.drop_index(op.f("ix_secret_aliases_id"), table_name="secret_aliases")
    op.drop_table("secret_aliases")
