"""
Database connection for CLI (shared with dashboard).

CLI connects directly to the same PostgreSQL database as the dashboard.
No more secrets.yml - everything is in the database.
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
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database URL (same as dashboard)
DATABASE_URL = os.getenv(
    "SUPERDEPLOY_DB_URL", "postgresql://localhost/superdeploy_dashboard"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ORM Models (same as dashboard/backend/models.py)
class Secret(Base):
    """Secret storage (replaces secrets.yml)."""

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
    """Secret aliases (replaces env_aliases in secrets.yml)."""

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
