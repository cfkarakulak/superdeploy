"""SQLAlchemy database models."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from cli.dashboard.backend.database import Base


class Project(Base):
    """Project model."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    environments = relationship("Environment", back_populates="project", cascade="all, delete-orphan")


class Environment(Base):
    """Environment model (production, staging, review)."""
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="environments")
    secrets = relationship("Secret", back_populates="environment", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uix_project_environment'),
    )


class Secret(Base):
    """Secret model."""
    __tablename__ = "secrets"
    
    id = Column(Integer, primary_key=True, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    app = Column(String(100), nullable=False, index=True)  # shared, api, services, storefront
    key = Column(String(255), nullable=False, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    environment = relationship("Environment", back_populates="secrets")
    
    __table_args__ = (
        UniqueConstraint('environment_id', 'app', 'key', name='uix_env_app_key'),
    )

