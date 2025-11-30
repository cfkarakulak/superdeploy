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
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    # project_type: 'application' (default) for app projects, 'orchestrator' for global infra
    project_type = Column(String(50), nullable=False, default="application", index=True)
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

    # Actual State (JSON: runtime state of VMs, addons, apps)
    # This is populated by sync.py after deployment events
    # Structure: {vms: {name: {ip, status}}, addons: {name: {status}}, apps: {name: {status}}}
    actual_state = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    apps = relationship("App", back_populates="project", cascade="all, delete-orphan")
    addons = relationship(
        "Addon", back_populates="project", cascade="all, delete-orphan"
    )
    vms = relationship("VM", back_populates="project", cascade="all, delete-orphan")
    secrets = relationship(
        "Secret", back_populates="project", cascade="all, delete-orphan"
    )
    secret_aliases = relationship(
        "SecretAlias", back_populates="project", cascade="all, delete-orphan"
    )


class ActivityLog(Base):
    """Activity log for audit trail."""

    __tablename__ = "activity_logs"
    __table_args__ = {"extend_existing": True}

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
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uix_project_app"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False, index=True)
    repo = Column(String(255), nullable=True)  # GitHub repo name
    owner = Column(String(255), nullable=True)  # GitHub owner/organization
    path = Column(String(500), nullable=True)  # Local path to app code
    vm = Column(String(50), nullable=True, default="app")  # VM role (app, core, etc)
    port = Column(Integer, nullable=True)  # Internal port
    external_port = Column(Integer, nullable=True)  # External port exposed
    domain = Column(String(200), nullable=True)
    replicas = Column(Integer, default=1)
    type = Column(String(50), nullable=True)
    services = Column(JSON, nullable=True)  # ["web", "worker", "scheduler", "beat"]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="apps")
    secrets = relationship("Secret", back_populates="app", cascade="all, delete-orphan")
    secret_aliases = relationship(
        "SecretAlias", back_populates="app", cascade="all, delete-orphan"
    )


class DeploymentHistory(Base):
    """Deployment history for rollback capability."""

    __tablename__ = "deployment_history"
    __table_args__ = {"extend_existing": True}

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
    """Secret storage in PostgreSQL with FK relationships."""

    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "app_id", "key", "environment", name="uix_secret"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_id = Column(
        Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=True, index=True
    )  # NULL = shared/project-level secret
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)  # Plain text storage
    environment = Column(String(50), default="production", nullable=False)
    source = Column(String(50), default="app", nullable=False)  # app/shared/addon
    editable = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="secrets")
    app = relationship("App", back_populates="secrets")


class SecretAlias(Base):
    """Secret aliases stored in PostgreSQL with FK relationships."""

    __tablename__ = "secret_aliases"
    __table_args__ = (
        UniqueConstraint("project_id", "app_id", "alias_key", name="uix_secret_alias"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_id = Column(
        Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias_key = Column(String(255), nullable=False)  # e.g. DB_HOST
    target_key = Column(String(255), nullable=False)  # e.g. postgres.primary.HOST
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="secret_aliases")
    app = relationship("App", back_populates="secret_aliases")


class Addon(Base):
    """Addon model - databases, queues, caches, proxy."""

    __tablename__ = "addons"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "category", "instance_name", name="uix_project_addon"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_name = Column(String(100), nullable=False)  # "primary", "secondary", etc
    category = Column(
        String(50), nullable=False, index=True
    )  # "databases", "queues", "caches", "proxy"
    type = Column(
        String(50), nullable=False
    )  # "postgres", "rabbitmq", "redis", "caddy"
    version = Column(String(50), nullable=False)
    vm = Column(String(50), nullable=False, default="core")
    plan = Column(String(50), nullable=True)  # "small", "standard", "large"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="addons")


class VM(Base):
    """VM configuration model."""

    __tablename__ = "vms"
    __table_args__ = (
        UniqueConstraint("project_id", "role", name="uix_project_vm_role"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), unique=True, nullable=True, index=True)
    role = Column(String(50), nullable=False)  # "core", "app", "scrape"
    external_ip = Column(String(50), nullable=True)  # Public IP
    internal_ip = Column(String(50), nullable=True)  # Private IP
    status = Column(String(50), nullable=True)  # provisioned, configured, etc
    count = Column(Integer, nullable=False, default=1)
    machine_type = Column(String(50), nullable=False, default="e2-medium")
    disk_size = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="vms")


class Setting(Base):
    """Global settings (not project-specific)."""

    __tablename__ = "settings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
