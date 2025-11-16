from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, AsyncIterator
from database import get_db
from models import Project, Environment, App, Addon, Secret
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


def generate_config_from_db(
    project: Project, apps: List[App], addons: List[Addon]
) -> Dict:
    """Generate config.yml structure from database models."""
    config = {
        "project": project.name,
        "gcp": {
            "project_id": project.gcp_project_id,
            "region": project.cloud_region,
        },
        "github": {
            "organization": project.github_org,
        },
        "apps": {},
        "addons": {},
    }

    # Add apps
    for app in apps:
        config["apps"][app.name] = {
            "repo": f"{app.owner}/{app.repo}",
            "owner": app.owner,
            "repo_name": app.repo,
            "vm": app.vm or "app",
            "port": app.port,
        }

    # Add addons
    for addon in addons:
        config["addons"][addon.name] = {
            "type": addon.type,
            "version": addon.version,
            "plan": addon.plan,
            "vm": addon.vm or "core",
        }

    return config


def generate_secrets_from_db(secrets: List[Secret]) -> Dict:
    """Generate secrets.yml structure from database models."""
    secrets_dict = {"secrets": {"shared": {}}}

    for secret in secrets:
        if secret.app == "shared":
            secrets_dict["secrets"]["shared"][secret.key] = secret.value
        else:
            if secret.app not in secrets_dict["secrets"]:
                secrets_dict["secrets"][secret.app] = {}
            secrets_dict["secrets"][secret.app][secret.key] = secret.value

    return secrets_dict


async def deploy_from_db(project_name: str, db: Session) -> AsyncIterator[str]:
    """Deploy project by reading from DB, generating files, and running CLI."""
    try:
        # 1. Read from DB
        yield (
            json.dumps(
                {
                    "type": "info",
                    "message": "📖 Reading project configuration from database...",
                }
            )
            + "\n"
        )

        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            yield (
                json.dumps(
                    {"type": "error", "message": f"Project '{project_name}' not found"}
                )
                + "\n"
            )
            return

        apps = db.query(App).filter(App.project_id == project.id).all()
        addons = db.query(Addon).filter(Addon.project_id == project.id).all()
        env = (
            db.query(Environment)
            .filter(
                Environment.project_id == project.id, Environment.name == "production"
            )
            .first()
        )

        if not env:
            yield (
                json.dumps(
                    {"type": "error", "message": "Production environment not found"}
                )
                + "\n"
            )
            return

        secrets = db.query(Secret).filter(Secret.environment_id == env.id).all()

        yield (
            json.dumps(
                {
                    "type": "info",
                    "message": f"✓ Found {len(apps)} apps, {len(addons)} addons, {len(secrets)} secrets",
                }
            )
            + "\n"
        )

        # 2. Generate config files
        yield (
            json.dumps(
                {"type": "info", "message": "📝 Generating configuration files..."}
            )
            + "\n"
        )

        superdeploy_root = Path(__file__).parent.parent.parent.parent
        project_dir = superdeploy_root / "projects" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Generate config.yml
        config_data = generate_config_from_db(project, apps, addons)
        config_path = project_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        yield (
            json.dumps({"type": "info", "message": f"✓ Generated {config_path}"}) + "\n"
        )

        # Generate secrets.yml
        secrets_data = generate_secrets_from_db(secrets)
        secrets_path = project_dir / "secrets.yml"
        with open(secrets_path, "w") as f:
            yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

        yield (
            json.dumps({"type": "info", "message": f"✓ Generated {secrets_path}"})
            + "\n"
        )

        # 3. Run CLI commands
        yield (
            json.dumps({"type": "info", "message": "🚀 Starting deployment..."}) + "\n"
        )

        # Use centralized CLI executor
        cli = get_cli()

        async for line in cli.execute(f"{project_name}:up"):
            decoded = line.strip()
            if decoded:
                yield json.dumps({"type": "log", "message": decoded}) + "\n"

        yield (
            json.dumps(
                {
                    "type": "success",
                    "message": "✅ Deployment completed successfully!",
                }
            )
            + "\n"
        )

    except Exception as e:
        yield json.dumps({"type": "error", "message": f"❌ Error: {str(e)}"}) + "\n"


@router.post("/{project_name}/deploy")
async def deploy_project(project_name: str, db: Session = Depends(get_db)):
    """Deploy project from database configuration."""
    return StreamingResponse(
        deploy_from_db(project_name, db), media_type="application/x-ndjson"
    )


@router.get("/{project_name}/vms")
def get_project_vms(project_name: str, db: Session = Depends(get_db)):
    """Get VMs for a project + orchestrator IP."""
    from models import VM

    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    vms = db.query(VM).filter(VM.project_id == project.id).all()

    # Get orchestrator IP
    orchestrator_project = (
        db.query(Project).filter(Project.name == "orchestrator").first()
    )
    orchestrator_ip = None
    if orchestrator_project:
        orchestrator_vm = (
            db.query(VM)
            .filter(VM.project_id == orchestrator_project.id, VM.name == "orchestrator")
            .first()
        )
        if orchestrator_vm:
            orchestrator_ip = orchestrator_vm.external_ip

    return {
        "orchestrator_ip": orchestrator_ip,
        "vms": [
            {
                "name": vm.name,
                "role": vm.role,
                "ip": vm.external_ip,
                "zone": vm.zone,
                "machine_type": vm.machine_type,
                "status": vm.status,
            }
            for vm in vms
        ],
    }
