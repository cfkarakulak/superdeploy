"""SQLAlchemy database models."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    JSON,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Project(Base):
    """Project model - stores all project configuration (replaces config.yml)."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    domain = Column(String(200), nullable=True)
    ssl_email = Column(String(200), nullable=True)

    # GitHub Configuration
    github_org = Column(String(100), nullable=True)

    # GCP Configuration
    gcp_project = Column(String(100), nullable=True)
    gcp_region = Column(String(50), nullable=True)
    gcp_zone = Column(String(50), nullable=True)

    # SSH Configuration
    ssh_key_path = Column(String(255), nullable=True)
    ssh_public_key_path = Column(String(255), nullable=True)
    ssh_user = Column(String(50), nullable=True)

    # Docker Configuration
    docker_registry = Column(String(200), nullable=True)
    docker_organization = Column(String(100), nullable=True)

    # Network Configuration
    vpc_subnet = Column(String(50), nullable=True)
    docker_subnet = Column(String(50), nullable=True)

    # VMs Configuration (JSON: {core: {count, machine_type, disk_size}, app: {...}})
    vms = Column(JSON, nullable=True)

    # Apps Configuration (JSON: {app_name: {path, vm, port, env}})
    apps_config = Column(JSON, nullable=True)

    # Addons Configuration (JSON: {databases: {primary: {type, version, ...}}, ...})
    addons_config = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    apps = relationship("App", back_populates="project", cascade="all, delete-orphan")


class ActivityLog(Base):
    """Activity log for audit trail."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    type = Column(
        String(50), nullable=False, index=True
    )  # deploy, scale, config, addon, restart
    actor = Column(String(100), nullable=True)  # User who triggered (for future auth)
    app_name = Column(String(100), nullable=True, index=True)
    event_data = Column(
        JSON, nullable=True
    )  # Additional context as JSON (renamed from metadata to avoid SQLAlchemy reserved word)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    project = relationship("Project")


class App(Base):
    """Application model."""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False, index=True)
    repo = Column(String(255), nullable=True)  # GitHub repo name
    owner = Column(String(255), nullable=True)  # GitHub owner/organization
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="apps")

    __table_args__ = (UniqueConstraint("project_id", "name", name="uix_project_app"),)


class DeploymentHistory(Base):
    """Deployment history for rollback capability."""

    __tablename__ = "deployment_history"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    app_name = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=False)  # Semantic version
    git_sha = Column(String(100), nullable=True)
    branch = Column(String(100), nullable=True)
    deployed_at = Column(DateTime, default=datetime.utcnow, index=True)
    deployed_by = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False)  # success, failed, in_progress
    duration = Column(Integer, nullable=True)  # Seconds
    event_data = Column(
        JSON, nullable=True
    )  # Commit message, files changed, etc. (renamed from metadata to avoid SQLAlchemy reserved word)

    project = relationship("Project")


class Secret(Base):
    """Secret storage in PostgreSQL."""

    __tablename__ = "secrets"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    app_name = Column(String(100), nullable=True, index=True)  # NULL = shared secret
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)  # Plain text storage
    environment = Column(String(50), default="production", nullable=False)
    source = Column(String(50), default="app", nullable=False)  # app/shared/addon
    editable = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "project_name", "app_name", "key", "environment", name="uix_secret"
        ),
    )


class SecretAlias(Base):
    """Secret aliases stored in PostgreSQL."""

    __tablename__ = "secret_aliases"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    app_name = Column(String(100), nullable=False, index=True)
    alias_key = Column(String(255), nullable=False)  # e.g. DB_HOST
    target_key = Column(String(255), nullable=False)  # e.g. postgres.primary.HOST
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "project_name", "app_name", "alias_key", name="uix_secret_alias"
        ),
    )


class Setting(Base):
    """Global settings (not project-specific)."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
