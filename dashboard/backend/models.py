"""SQLAlchemy database models."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Setting(Base):
    """Application settings model."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    encrypted = Column(Integer, default=0)  # 0 = plain, 1 = encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(Base):
    """Project model."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    gcp_project_id = Column(String(200), nullable=True)  # GCP Project ID
    github_org = Column(String(100), nullable=True)  # GitHub organization
    domain = Column(String(200), nullable=True)  # e.g., "cheapa.io"
    cloud_provider = Column(String(50), default="gcp")
    cloud_region = Column(String(100), default="us-central1")
    cloud_zone = Column(String(100), default="us-central1-a")
    created_at = Column(DateTime, default=datetime.utcnow)

    environments = relationship(
        "Environment", back_populates="project", cascade="all, delete-orphan"
    )
    apps = relationship("App", back_populates="project", cascade="all, delete-orphan")
    addons = relationship(
        "Addon", back_populates="project", cascade="all, delete-orphan"
    )
    vms = relationship("VM", back_populates="project", cascade="all, delete-orphan")


class VM(Base):
    """Virtual Machine model."""

    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)  # e.g., "cheapa-app-0"
    role = Column(String(50), nullable=False)  # e.g., "app", "core"
    external_ip = Column(String(50), nullable=True)
    internal_ip = Column(String(50), nullable=True)
    zone = Column(String(100), nullable=True)
    machine_type = Column(String(100), nullable=True)
    status = Column(String(50), default="running")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="vms")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uix_project_vm_name"),
    )


class Environment(Base):
    """Environment model (production, staging, review)."""

    __tablename__ = "environments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="environments")
    secrets = relationship(
        "Secret", back_populates="environment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uix_project_environment"),
    )


class Secret(Base):
    """Secret model."""

    __tablename__ = "secrets"

    id = Column(Integer, primary_key=True, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    app = Column(
        String(100), nullable=False, index=True
    )  # shared, api, services, storefront
    key = Column(String(255), nullable=False, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    environment = relationship("Environment", back_populates="secrets")

    __table_args__ = (
        UniqueConstraint("environment_id", "app", "key", name="uix_env_app_key"),
    )


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


class MetricsCache(Base):
    """Cached container metrics for performance."""

    __tablename__ = "metrics_cache"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    vm_name = Column(String(100), nullable=False, index=True)
    container_name = Column(String(200), nullable=False, index=True)
    cpu_percent = Column(Float, nullable=True)
    memory_usage = Column(String(50), nullable=True)  # e.g., "256MB / 512MB"
    memory_percent = Column(Float, nullable=True)
    network_rx = Column(String(50), nullable=True)  # e.g., "1.2GB"
    network_tx = Column(String(50), nullable=True)  # e.g., "850MB"
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    project = relationship("Project")


class App(Base):
    """Application model."""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # web, worker, cron
    vm = Column(String(100), nullable=True)  # VM name reference (not FK for simplicity)
    domain = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    dockerfile_path = Column(String(255), nullable=True)
    processes = Column(
        JSON, nullable=True
    )  # {"web": {"command": "...", "replicas": 1}}
    repo = Column(String(255), nullable=True)  # GitHub repo name
    owner = Column(String(255), nullable=True)  # GitHub owner/organization
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="apps")

    __table_args__ = (UniqueConstraint("project_id", "name", name="uix_project_app"),)


class Addon(Base):
    """Addon model (postgres, redis, etc)."""

    __tablename__ = "addons"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # postgres, redis, rabbitmq, etc
    category = Column(String(50), nullable=False)  # databases, caches, queues
    version = Column(String(50), nullable=True)  # e.g., "15-alpine", "7-alpine"
    vm = Column(String(100), nullable=True)  # VM name reference
    plan = Column(String(50), default="standard")
    status = Column(String(50), default="running")
    credentials = Column(JSON, nullable=True)  # Stored credentials
    attachments = Column(
        JSON, nullable=True
    )  # [{"app_name": "api", "as_prefix": "DATABASE"}]
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="addons")

    __table_args__ = (
        UniqueConstraint("project_id", "category", "name", name="uix_project_addon"),
    )


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
