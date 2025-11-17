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
    """Project model - minimal metadata."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    domain = Column(String(200), nullable=True)  # e.g., "cheapa.io"
    github_org = Column(String(100), nullable=True)  # GitHub organization
    created_at = Column(DateTime, default=datetime.utcnow)

    apps = relationship("App", back_populates="project", cascade="all, delete-orphan")
    
    # Note: VMs, cloud provider, region, zone etc. are fetched from CLI


# VM table removed - use CLI `project:status --json` instead


# Environment table removed - use hardcoded ["production", "staging"] instead


# Secret table removed - use CLI `project:config:list/set/unset` instead


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


# MetricsCache table removed - use Prometheus real-time queries instead


class App(Base):
    """Application model - minimal metadata for GitHub integration."""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False, index=True)
    repo = Column(String(255), nullable=True)  # GitHub repo name
    owner = Column(String(255), nullable=True)  # GitHub owner/organization
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="apps")

    __table_args__ = (UniqueConstraint("project_id", "name", name="uix_project_app"),)
    
    # Note: All other app data (type, vm, domain, port, processes, etc.) 
    # is fetched from CLI: `project:status -a app --json`


# Addon table removed - use CLI `project:status -a app --json` instead


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
