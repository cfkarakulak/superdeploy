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
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database URL (same as dashboard)
DATABASE_URL = os.getenv("SUPERDEPLOY_DB_URL", "postgresql://localhost/superdeploy")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ORM Models (same as dashboard/backend/models.py)
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


class App(Base):
    """Application model."""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    repo = Column(String(255), nullable=False)
    owner = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
