"""Project CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from dashboard.backend.database import get_db
from dashboard.backend.models import Project, Environment

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str

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
    # Check if project exists
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


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and all its environments/secrets."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/sync")
def sync_projects_from_filesystem(db: Session = Depends(get_db)):
    """Sync projects from filesystem to database."""
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    projects_dir = project_root / "projects"

    if not projects_dir.exists():
        return {"synced": 0, "projects": []}

    synced_projects = []
    synced_count = 0

    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith("."):
            config_file = project_dir / "config.yml"
            if config_file.exists():
                # Check if project exists in DB
                existing = (
                    db.query(Project).filter(Project.name == project_dir.name).first()
                )

                if not existing:
                    # Create project
                    new_project = Project(name=project_dir.name)
                    db.add(new_project)
                    db.flush()

                    # Create default environments
                    for env_name in ["production", "staging", "review"]:
                        env = Environment(name=env_name, project_id=new_project.id)
                        db.add(env)

                    db.commit()
                    synced_count += 1
                    synced_projects.append(project_dir.name)

    return {"synced": synced_count, "projects": synced_projects}


@router.get("/{project_name}/config")
def get_project_config(project_name: str):
    """Get project configuration from config.yml."""
    import yaml
    from pathlib import Path

    config_path = (
        Path(__file__).parent.parent.parent.parent
        / "projects"
        / project_name
        / "config.yml"
    )

    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Project config not found")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


@router.get("/{project_name}/status")
def get_project_status(project_name: str):
    """Get project status (ps command output)."""
    import subprocess
    from pathlib import Path
    import re

    project_root = Path(__file__).parent.parent.parent.parent

    # Function to strip ANSI codes
    def strip_ansi(text):
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text).strip()

    try:
        result = subprocess.run(
            [
                str(project_root / "venv" / "bin" / "python"),
                "-m",
                "cli.main",
                f"{project_name}:ps",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=30,
        )

        # Parse ps output
        lines = result.stdout.strip().split("\n")
        apps = []

        # Simple parsing - look for app info in table
        for line in lines:
            line = strip_ansi(line).strip()
            if (
                "│" in line
                and not line.startswith("┃")
                and not line.startswith("┏")
                and not line.startswith("┡")
                and not line.startswith("└")
            ):
                parts = [strip_ansi(p).strip() for p in line.split("│") if p.strip()]
                if len(parts) >= 6 and parts[0] not in ["App", ""]:
                    apps.append(
                        {
                            "app": parts[0],
                            "type": parts[1],
                            "replicas": parts[2],
                            "port": parts[3],
                            "vm": parts[4],
                            "status": parts[5],
                        }
                    )

        return {"apps": apps, "total": len(apps)}
    except Exception as e:
        return {"apps": [], "total": 0, "error": str(e)}
