"""Create secrets table"""

from alembic import op
import sqlalchemy as sa


revision = "20251118111205"
down_revision = "20251118111204"
branch_labels = None
depends_on = None


def upgrade():
    """Create secrets table."""
    op.create_table(
        "secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=100), nullable=False),
        sa.Column("app_name", sa.String(length=100), nullable=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("editable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_name", "app_name", "key", "environment", name="uix_secret"
        ),
    )
    op.create_index(op.f("ix_secrets_id"), "secrets", ["id"], unique=False)
    op.create_index(
        op.f("ix_secrets_project_name"), "secrets", ["project_name"], unique=False
    )
    op.create_index(op.f("ix_secrets_app_name"), "secrets", ["app_name"], unique=False)


def downgrade():
    """Drop secrets table."""
    op.drop_table("secrets")
