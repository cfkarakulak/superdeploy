from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Project, App
import json
from cache import get_cache, set_cache, CACHE_TTL

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
    domain: str
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
    """Create a new project from wizard by generating config files."""
    import yaml
    from pathlib import Path

    # Check if project already exists
    existing = db.query(Project).filter(Project.name == payload.project_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project already exists")

    # Get project root (4 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent
    project_dir = project_root / "projects" / payload.project_name

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create config.yml
    config_data = {
        "project": payload.project_name,
        "gcp_project": payload.gcp_project,
        "gcp_region": payload.gcp_region,
        "github_org": payload.github_org,
        "apps": {},
    }

    # Add apps to config
    for app in payload.apps:
        config_data["apps"][app.name] = {
            "repo": app.repo,
            "port": app.port,
            "vm": "app",
        }

    # Add addons to config
    addons_dict = payload.addons.dict()
    if any(addons_dict.values()):
        config_data["addons"] = {}

        if addons_dict.get("databases"):
            config_data["addons"]["databases"] = {
                addon: {
                    "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest")
                }
                for addon in addons_dict["databases"]
            }

        if addons_dict.get("queues"):
            config_data["addons"]["queues"] = {
                addon: {
                    "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest")
                }
                for addon in addons_dict["queues"]
            }

        if addons_dict.get("caches"):
            config_data["addons"]["caches"] = {
                addon: {
                    "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest")
                }
                for addon in addons_dict["caches"]
            }

        if addons_dict.get("proxy"):
            config_data["addons"]["proxy"] = {
                addon: {
                    "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest")
                }
                for addon in addons_dict["proxy"]
            }

    # Write config.yml
    config_path = project_dir / "config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    # 2. Create secrets.yml
    secrets_data = {
        "shared": {
            "DOCKER_ORG": payload.secrets.docker_org,
            "DOCKER_USERNAME": payload.secrets.docker_username,
            "DOCKER_TOKEN": payload.secrets.docker_token,
            "GITHUB_TOKEN": payload.secrets.github_token,
        },
        "apps": {},
    }

    # Add app-specific empty sections
    for app in payload.apps:
        secrets_data["apps"][app.name] = {}

    # Write secrets.yml
    secrets_path = project_dir / "secrets.yml"
    with open(secrets_path, "w") as f:
        yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

    # Set restrictive permissions on secrets.yml
    secrets_path.chmod(0o600)

    # 3. Create project in database
    db_project = Project(
        name=payload.project_name, domain=payload.domain, github_org=payload.github_org
    )
    db.add(db_project)
    db.flush()

    # 4. Create apps in database
    for app_data in payload.apps:
        repo_parts = app_data.repo.split("/")
        owner = repo_parts[0] if len(repo_parts) > 0 else ""
        repo_name = repo_parts[1] if len(repo_parts) > 1 else app_data.repo

        app = App(
            project_id=db_project.id, name=app_data.name, repo=repo_name, owner=owner
        )
        db.add(app)

    db.commit()
    db.refresh(db_project)

    return db_project


@router.get("/{project_name}/vms")
def get_project_vms(project_name: str):
    """Get VMs for a project + orchestrator IP from CLI (with Redis cache)."""
    import subprocess

    # Check cache first
    cache_key = f"vms:{project_name}"
    cached = get_cache(cache_key)
    if cached:
        return cached

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

        response = {
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

        # Cache for 5 minutes
        set_cache(cache_key, response, CACHE_TTL["vms"])

        return response

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse CLI output: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
