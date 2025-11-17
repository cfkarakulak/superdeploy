from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, AsyncIterator
from database import get_db
from models import Project, App
from pathlib import Path
from utils.cli import get_cli
import json
import yaml

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


class AppCreate(BaseModel):
    name: str
    repo: str  # "owner/repo" format
    port: int


class AddonsCreate(BaseModel):
    databases: List[str] = []
    queues: List[str] = []
    proxy: List[str] = []
    caches: List[str] = []


class SecretsCreate(BaseModel):
    docker_org: str
    docker_username: str
    docker_token: str
    github_token: str  # Single token with repo, workflow, packages, admin:org scopes
    smtp_host: str = ""
    smtp_port: str = ""
    smtp_user: str = ""
    smtp_password: str = ""


class WizardProjectCreate(BaseModel):
    project_name: str
    gcp_project: str
    gcp_region: str
    github_org: str
    apps: List[AppCreate]
    addons: AddonsCreate
    secrets: SecretsCreate


class ProjectResponse(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None
    gcp_project_id: Optional[str] = None
    github_org: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all projects from database (excluding orchestrator)."""
    projects = db.query(Project).filter(Project.name != "orchestrator").all()
    return projects


@router.post("/", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    # Check if project already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project already exists")

    # Create project
    db_project = Project(name=project.name)
    db.add(db_project)
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


# Addon version mapping
ADDON_VERSIONS = {
    "postgres": {"version": "15-alpine", "vm": "core"},
    "mysql": {"version": "8-alpine", "vm": "core"},
    "mongodb": {"version": "7", "vm": "core"},
    "rabbitmq": {"version": "3.12", "vm": "core"},
    "caddy": {"version": "2-alpine", "vm": "core"},
    "nginx": {"version": "alpine", "vm": "core"},
    "redis": {"version": "7-alpine", "vm": "core"},
    "memcached": {"version": "alpine", "vm": "core"},
}


@router.post("/wizard", response_model=ProjectResponse)
def create_project_from_wizard(
    payload: WizardProjectCreate, db: Session = Depends(get_db)
):
    """Create a new project from wizard with all configuration."""
    # Check if project already exists
    existing = db.query(Project).filter(Project.name == payload.project_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project already exists")

    # 1. Create project
    project = Project(
        name=payload.project_name,
        gcp_project_id=payload.gcp_project,
        cloud_region=payload.gcp_region,
        github_org=payload.github_org,
    )
    db.add(project)
    db.flush()

    # 2. Create production environment
    env = Environment(name="production", project_id=project.id)
    db.add(env)
    db.flush()

    # 3. Create apps
    for app_data in payload.apps:
        repo_parts = app_data.repo.split("/")
        owner = repo_parts[0] if len(repo_parts) > 0 else ""
        repo_name = repo_parts[1] if len(repo_parts) > 1 else app_data.repo

        app = App(
            project_id=project.id,
            name=app_data.name,
            repo=repo_name,
            owner=owner,
            port=app_data.port,
            type="web",  # default
            vm="app",  # default
        )
        db.add(app)

    # 4. Create addons
    category_map = {
        "databases": "databases",
        "queues": "queues",
        "proxy": "proxy",
        "caches": "caches",
    }

    for category_key, addon_ids in payload.addons.dict().items():
        category = category_map.get(category_key, category_key)
        for addon_id in addon_ids:
            addon_meta = ADDON_VERSIONS.get(
                addon_id, {"version": "latest", "vm": "core"}
            )

            addon = Addon(
                project_id=project.id,
                name=addon_id,
                type=addon_id,
                category=category,
                version=addon_meta["version"],
                vm=addon_meta["vm"],
                plan="standard",
                status="pending",
            )
            db.add(addon)

    # 5. Create secrets (in production environment)
    secrets_map = {
        "DOCKER_ORG": payload.secrets.docker_org,
        "DOCKER_USERNAME": payload.secrets.docker_username,
        "DOCKER_TOKEN": payload.secrets.docker_token,
        "REPOSITORY_TOKEN": payload.secrets.github_token,
    }

    if payload.secrets.smtp_host:
        secrets_map.update(
            {
                "SMTP_HOST": payload.secrets.smtp_host,
                "SMTP_PORT": payload.secrets.smtp_port,
                "SMTP_USER": payload.secrets.smtp_user,
                "SMTP_PASSWORD": payload.secrets.smtp_password,
            }
        )

    for key, value in secrets_map.items():
        if value:  # Only add non-empty secrets
            secret = Secret(environment_id=env.id, app="shared", key=key, value=value)
            db.add(secret)

    db.commit()
    db.refresh(project)

    return project


@router.get("/{project_name}/vms")
def get_project_vms(project_name: str):
    """Get VMs for a project + orchestrator IP from CLI."""
    import subprocess

    try:
        # Get project VMs
        result = subprocess.run(
            ["./superdeploy.sh", f"{project_name}:status", "--json"],
            capture_output=True,
            text=True,
            cwd="/Users/cfkarakulak/Desktop/cheapa.io/hero/superdeploy",
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Failed to get VMs: {result.stderr}"
            )

        project_data = json.loads(result.stdout)

        # Get orchestrator IP
        orch_result = subprocess.run(
            ["./superdeploy.sh", "orchestrator:status", "--json"],
            capture_output=True,
            text=True,
            cwd="/Users/cfkarakulak/Desktop/cheapa.io/hero/superdeploy",
        )

        orchestrator_ip = None
        if orch_result.returncode == 0:
            orch_data = json.loads(orch_result.stdout)
            if orch_data.get("vms"):
                # Find orchestrator VM
                for vm in orch_data["vms"]:
                    if vm.get("name") == "orchestrator":
                        orchestrator_ip = vm.get("ip")
                        break

        return {
            "orchestrator_ip": orchestrator_ip,
            "vms": [
                {
                    "name": vm.get("name"),
                    "role": vm.get("role"),
                    "ip": vm.get("ip"),
                    "zone": vm.get("zone"),
                    "machine_type": vm.get("machine_type"),
                    "status": vm.get("status", "unknown"),
                }
                for vm in project_data.get("vms", [])
            ],
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse CLI output: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
