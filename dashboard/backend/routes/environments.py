"""Environment CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
from models import Environment

router = APIRouter(tags=["environments"])


class EnvironmentResponse(BaseModel):
    id: int
    name: str
    project_id: int

    class Config:
        from_attributes = True


@router.get("/project/{project_id}", response_model=List[EnvironmentResponse])
def list_environments(project_id: int, db: Session = Depends(get_db)):
    """List all environments for a project."""
    environments = (
        db.query(Environment).filter(Environment.project_id == project_id).all()
    )
    return environments


@router.get("/{environment_id}", response_model=EnvironmentResponse)
def get_environment(environment_id: int, db: Session = Depends(get_db)):
    """Get environment by ID."""
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return environment
