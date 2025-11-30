"""Create vms table

Revision ID: 20251118111209
Revises: 20251118111208
Create Date: 2025-11-18 11:12:09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118111209"
down_revision = "20251118111208"
branch_labels = None
depends_on = None


def upgrade():
    """Create vms table with all necessary columns."""
    op.create_table(
        "vms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=True
        ),  # VM name like "cheapa-app-0"
        sa.Column(
            "role", sa.String(length=50), nullable=False
        ),  # "core", "app", "scrape"
        sa.Column("external_ip", sa.String(length=50), nullable=True),  # Public IP
        sa.Column("internal_ip", sa.String(length=50), nullable=True),  # Private IP
        sa.Column(
            "status", sa.String(length=50), nullable=True
        ),  # provisioned, configured, etc
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "machine_type",
            sa.String(length=50),
            nullable=False,
            server_default="e2-medium",
        ),
        sa.Column("disk_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "role", name="uix_project_vm_role"),
    )
    op.create_index(op.f("ix_vms_id"), "vms", ["id"], unique=False)
    op.create_index(op.f("ix_vms_project_id"), "vms", ["project_id"], unique=False)
    op.create_index(op.f("ix_vms_name"), "vms", ["name"], unique=True)


def downgrade():
    """Drop vms table."""
    op.drop_index(op.f("ix_vms_name"), table_name="vms")
    op.drop_index(op.f("ix_vms_project_id"), table_name="vms")
    op.drop_index(op.f("ix_vms_id"), table_name="vms")
    op.drop_table("vms")
