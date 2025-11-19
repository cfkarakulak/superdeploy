"""Database connection and session management."""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Local PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://localhost/superdeploy"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Project(Base):
    """Project model."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    vms = Column(JSON)
    apps_config = Column(JSON)
    addons_config = Column(JSON)
    network_config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class VM(Base):
    """VM model."""
    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    role = Column(String(50))
    external_ip = Column(String(50))
    internal_ip = Column(String(50))
    machine_type = Column(String(50))
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
