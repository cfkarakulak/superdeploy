"""Create projects table"""

from alembic import op
import sqlalchemy as sa


revision = "20251118111201"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create projects table."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("ssl_email", sa.String(length=200), nullable=True),
        sa.Column("github_org", sa.String(length=100), nullable=True),
        sa.Column("gcp_project", sa.String(length=100), nullable=True),
        sa.Column("gcp_region", sa.String(length=50), nullable=True),
        sa.Column("gcp_zone", sa.String(length=50), nullable=True),
        sa.Column("ssh_key_path", sa.String(length=255), nullable=True),
        sa.Column("ssh_public_key_path", sa.String(length=255), nullable=True),
        sa.Column("ssh_user", sa.String(length=50), nullable=True),
        sa.Column("docker_registry", sa.String(length=200), nullable=True),
        sa.Column("docker_organization", sa.String(length=100), nullable=True),
        sa.Column("vpc_subnet", sa.String(length=50), nullable=True),
        sa.Column("docker_subnet", sa.String(length=50), nullable=True),
        sa.Column("vms", sa.JSON(), nullable=True),
        sa.Column("apps_config", sa.JSON(), nullable=True),
        sa.Column("addons_config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=True)


def downgrade():
    """Drop projects table."""
    op.drop_table("projects")
