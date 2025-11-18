"""Create secret_aliases table"""

from alembic import op
import sqlalchemy as sa


revision = "20251118111206"
down_revision = "20251118111205"
branch_labels = None
depends_on = None


def upgrade():
    """Create secret_aliases table."""
    op.create_table(
        "secret_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=100), nullable=False),
        sa.Column("app_name", sa.String(length=100), nullable=False),
        sa.Column("alias_key", sa.String(length=255), nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_name", "app_name", "alias_key", name="uix_secret_alias"
        ),
    )
    op.create_index(
        op.f("ix_secret_aliases_id"), "secret_aliases", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_secret_aliases_project_name"),
        "secret_aliases",
        ["project_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_secret_aliases_app_name"), "secret_aliases", ["app_name"], unique=False
    )


def downgrade():
    """Drop secret_aliases table."""
    op.drop_table("secret_aliases")
