from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Project, Environment

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all projects from database."""
    projects = db.query(Project).all()
    return projects


@router.post("/", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project with default environments."""
    # Check if project already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project already exists")

    # Create project
    db_project = Project(name=project.name)
    db.add(db_project)
    db.flush()

    # Create default environments
    for env_name in ["production", "staging", "review"]:
        env = Environment(name=env_name, project_id=db_project.id)
        db.add(env)

    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/{project_name}", response_model=ProjectResponse)
def get_project(project_name: str, db: Session = Depends(get_db)):
    """Get a single project by name."""
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
