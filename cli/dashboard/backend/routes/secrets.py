"""Secret CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from cli.dashboard.backend.database import get_db
from cli.dashboard.backend.models import Secret

router = APIRouter(tags=["secrets"])


class SecretCreate(BaseModel):
    environment_id: int
    app: str
    key: str
    value: str


class SecretUpdate(BaseModel):
    value: str


class SecretResponse(BaseModel):
    id: int
    environment_id: int
    app: str
    key: str
    value: str
    
    class Config:
        from_attributes = True


@router.get("/environment/{environment_id}", response_model=List[SecretResponse])
def list_secrets(environment_id: int, db: Session = Depends(get_db)):
    """List all secrets for an environment."""
    secrets = db.query(Secret).filter(Secret.environment_id == environment_id).all()
    return secrets


@router.get("/{secret_id}", response_model=SecretResponse)
def get_secret(secret_id: int, db: Session = Depends(get_db)):
    """Get secret by ID."""
    secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    return secret


@router.post("/", response_model=SecretResponse)
def create_secret(secret: SecretCreate, db: Session = Depends(get_db)):
    """Create a new secret."""
    # Check if secret already exists
    existing = db.query(Secret).filter(
        Secret.environment_id == secret.environment_id,
        Secret.app == secret.app,
        Secret.key == secret.key
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Secret with this key already exists")
    
    db_secret = Secret(**secret.dict())
    db.add(db_secret)
    db.commit()
    db.refresh(db_secret)
    return db_secret


@router.put("/{secret_id}", response_model=SecretResponse)
def update_secret(secret_id: int, secret_update: SecretUpdate, db: Session = Depends(get_db)):
    """Update a secret value."""
    db_secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not db_secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    
    db_secret.value = secret_update.value
    db.commit()
    db.refresh(db_secret)
    return db_secret


@router.delete("/{secret_id}")
def delete_secret(secret_id: int, db: Session = Depends(get_db)):
    """Delete a secret."""
    db_secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not db_secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    
    db.delete(db_secret)
    db.commit()
    return {"ok": True}

