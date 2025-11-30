"""
Database connection for CLI (shared with dashboard).

CLI connects directly to the same PostgreSQL database as the dashboard.
All secrets are stored in the database.
"""

import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    UniqueConstraint,
    JSON,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Database URL (same as dashboard)
DATABASE_URL = os.getenv("SUPERDEPLOY_DB_URL", "postgresql://localhost/superdeploy")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Project(Base):
    """Project model - stores all project configuration (replaces config.yml)."""

    __tablename__ = "projects"

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

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    apps = relationship("App", back_populates="project", cascade="all, delete-orphan")
    secrets = relationship(
        "Secret", back_populates="project", cascade="all, delete-orphan"
    )
    secret_aliases = relationship(
        "SecretAlias", back_populates="project", cascade="all, delete-orphan"
    )
    addons = relationship(
        "Addon", back_populates="project", cascade="all, delete-orphan"
    )
    vms = relationship("VM", back_populates="project", cascade="all, delete-orphan")


class App(Base):
    """Application model."""

    __tablename__ = "apps"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uix_project_app"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False, index=True)
    repo = Column(String(255), nullable=True)
    owner = Column(String(100), nullable=True)
    path = Column(String(500), nullable=True)
    vm = Column(String(50), nullable=True, default="app")
    port = Column(Integer, nullable=True)
    external_port = Column(Integer, nullable=True)
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


class Secret(Base):
    """Secret storage in PostgreSQL with proper FK relationships."""

    __tablename__ = "secrets"

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
    last_synced_at = Column(DateTime, nullable=True)  # Track GitHub sync time

    __table_args__ = (
        UniqueConstraint(
            "project_id", "app_id", "key", "environment", name="uix_secret"
        ),
    )

    # Relationships
    project = relationship("Project", back_populates="secrets")
    app = relationship("App", back_populates="secrets")


class SecretAlias(Base):
    """Secret aliases stored in PostgreSQL with proper FK relationships."""

    __tablename__ = "secret_aliases"

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

    __table_args__ = (
        UniqueConstraint("project_id", "app_id", "alias_key", name="uix_secret_alias"),
    )

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
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    vm = Column(String(50), nullable=False, default="core")
    plan = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="addons")


class VM(Base):
    """VM configuration model."""

    __tablename__ = "vms"
    __table_args__ = (
        UniqueConstraint("project_id", "role", name="uix_project_vm_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(
        String(100), unique=True, nullable=True, index=True
    )  # VM name like "cheapa-app-0"
    role = Column(String(50), nullable=False)
    external_ip = Column(String(50), nullable=True)  # Public IP
    internal_ip = Column(String(50), nullable=True)  # Private IP
    status = Column(String(50), nullable=True)  # provisioned, configured, etc
    count = Column(Integer, nullable=False, default=1)
    machine_type = Column(String(50), nullable=False, default="e2-medium")
    disk_size = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="vms")


class ActivityLog(Base):
    """Activity log model - audit trail for all operations."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    actor = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db_session():
    """Get database session."""
    return SessionLocal()


def test_connection():
    """Test database connection."""
    try:
        db = get_db_session()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
