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
    description: Optional[str] = None
    domain: Optional[str] = None
    ssl_email: Optional[str] = None
    github_org: Optional[str] = None
    gcp_project: Optional[str] = None
    gcp_region: Optional[str] = None
    gcp_zone: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_public_key_path: Optional[str] = None
    ssh_user: Optional[str] = None
    docker_registry: Optional[str] = None
    docker_organization: Optional[str] = None
    vpc_subnet: Optional[str] = None
    docker_subnet: Optional[str] = None
    vms: Optional[dict] = None
    apps_config: Optional[dict] = None
    addons_config: Optional[dict] = None

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


@router.get("/{project_name}/apps")
def get_project_apps(project_name: str, db: Session = Depends(get_db)):
    """Get all apps for a project."""
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    apps = db.query(App).filter(App.project_id == project.id).all()
    return apps


@router.post("/{project_name}/down")
async def teardown_project(project_name: str, db: Session = Depends(get_db)):
    """Teardown project infrastructure and delete from database."""
    from fastapi.responses import StreamingResponse
    import asyncio
    import re
    from models import Secret, App

    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    def strip_ansi_codes(text: str) -> str:
        """Remove ANSI color codes from text."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    async def generate_logs():
        try:
            # Run CLI down command with --yes flag
            process = await asyncio.create_subprocess_exec(
                "superdeploy",
                f"{project_name}:down",
                "--yes",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd="/Users/cfkarakulak/Desktop/cheapa.io/hero/superdeploy",
            )

            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode().strip()
                    if decoded_line:
                        # Strip ANSI codes
                        clean_line = strip_ansi_codes(decoded_line)
                        if clean_line:
                            yield f"data: {clean_line}\n\n"

            await process.wait()

            if process.returncode == 0:
                # Delete from database after successful teardown
                db.query(Secret).filter(Secret.project_name == project_name).delete()
                db.query(App).filter(App.project_id == project.id).delete()
                db.delete(project)
                db.commit()

                yield f"data: ✓ Project '{project_name}' deleted successfully from database\n\n"
            else:
                yield f"data: ✗ Failed to teardown project (exit code: {process.returncode})\n\n"

        except Exception as e:
            yield f"data: ✗ Error: {str(e)}\n\n"

    return StreamingResponse(generate_logs(), media_type="text/event-stream")


@router.delete("/{project_name}")
def delete_project(project_name: str, db: Session = Depends(get_db)):
    """Delete a project and all its associated data (without infrastructure teardown)."""
    from models import Secret, App

    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete associated secrets
    db.query(Secret).filter(Secret.project_name == project_name).delete()

    # Delete associated apps (cascade will handle this, but explicit is better)
    db.query(App).filter(App.project_id == project.id).delete()

    # Delete project
    db.delete(project)
    db.commit()

    return {"message": f"Project '{project_name}' deleted successfully"}


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
    """Create a new project from wizard - all config stored in database."""
    from pathlib import Path
    from models import Secret

    # Check if project already exists
    existing = db.query(Project).filter(Project.name == payload.project_name).first()

    # Get project root (4 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent
    project_dir = project_root / "projects" / payload.project_name

    # Create project directory (for future files like docker-compose, etc)
    project_dir.mkdir(parents=True, exist_ok=True)

    # If project exists, update it instead of failing
    if existing:
        # Delete existing apps and secrets to recreate
        db.query(App).filter(App.project_id == existing.id).delete()
        db.query(Secret).filter(Secret.project_name == payload.project_name).delete()
        db.flush()

    # Build apps configuration
    apps_config = {}
    for app in payload.apps:
        # Parse repo owner/name
        repo_parts = app.repo.split("/")
        owner = repo_parts[0] if len(repo_parts) > 0 else payload.github_org
        repo_name = repo_parts[1] if len(repo_parts) > 1 else app.repo

        apps_config[app.name] = {
            "repo": app.repo,
            "port": app.port,
            "vm": "app",
            "type": "python",  # Default type, can be changed in database
            "path": f"~/repos/{owner}/{repo_name}",  # Required for marker file reading
        }

    # Build addons configuration
    addons_config = {}
    addons_dict = payload.addons.dict()

    if addons_dict.get("databases"):
        addons_config["databases"] = {}
        for addon in addons_dict["databases"]:
            addons_config["databases"][addon] = {
                "type": addon,
                "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest"),
                "vm": ADDON_VERSIONS.get(addon, {}).get("vm", "core"),
            }

    if addons_dict.get("queues"):
        addons_config["queues"] = {}
        for addon in addons_dict["queues"]:
            addons_config["queues"][addon] = {
                "type": addon,
                "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest"),
                "vm": ADDON_VERSIONS.get(addon, {}).get("vm", "core"),
            }

    if addons_dict.get("caches"):
        addons_config["caches"] = {}
        for addon in addons_dict["caches"]:
            addons_config["caches"][addon] = {
                "type": addon,
                "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest"),
                "vm": ADDON_VERSIONS.get(addon, {}).get("vm", "core"),
            }

    if addons_dict.get("proxy"):
        addons_config["proxy"] = {}
        for addon in addons_dict["proxy"]:
            addons_config["proxy"][addon] = {
                "type": addon,
                "version": ADDON_VERSIONS.get(addon, {}).get("version", "latest"),
                "vm": ADDON_VERSIONS.get(addon, {}).get("vm", "core"),
            }

    # Build VMs configuration (default setup)
    vms_config = {
        "core": {
            "count": 1,
            "machine_type": "e2-medium",
            "disk_size": 20,
            "services": [],
        },
        "app": {
            "count": 1,
            "machine_type": "e2-medium",
            "disk_size": 30,
            "services": [],
        },
    }

    # CRITICAL: Add Caddy to EVERY VM (required for app routing)
    # Even if user didn't select proxy in wizard, Caddy must be on every VM
    if "proxy" not in addons_config:
        addons_config["proxy"] = {}

    for vm_name in vms_config.keys():
        # Add Caddy instance for this VM if not already exists
        if vm_name not in addons_config["proxy"]:
            addons_config["proxy"][vm_name] = {
                "type": "caddy",
                "version": "2-alpine",
                "vm": vm_name,
            }

    # Determine GCP zone from region
    gcp_zone = f"{payload.gcp_region}-a" if payload.gcp_region else "us-central1-a"

    # Create or update project in database with ALL configuration
    if existing:
        # Update existing project
        db_project = existing
        db_project.description = f"{payload.project_name} project"
        db_project.domain = payload.domain
        db_project.ssl_email = f"admin@{payload.domain}" if payload.domain else None
        db_project.github_org = payload.github_org
        db_project.gcp_project = payload.gcp_project
        db_project.gcp_region = payload.gcp_region
        db_project.gcp_zone = gcp_zone
        db_project.ssh_key_path = "~/.ssh/superdeploy_deploy"
        db_project.ssh_public_key_path = "~/.ssh/superdeploy_deploy.pub"
        db_project.ssh_user = "superdeploy"
        db_project.docker_registry = "docker.io"
        db_project.docker_organization = payload.secrets.docker_org
        db_project.vpc_subnet = "10.1.0.0/16"
        db_project.docker_subnet = "172.30.0.0/24"
        db_project.vms = vms_config
        db_project.apps_config = apps_config
        db_project.addons_config = addons_config
        db.flush()
    else:
        # Create new project
        db_project = Project(
            name=payload.project_name,
            description=f"{payload.project_name} project",
            domain=payload.domain,
            ssl_email=f"admin@{payload.domain}" if payload.domain else None,
            github_org=payload.github_org,
            gcp_project=payload.gcp_project,
            gcp_region=payload.gcp_region,
            gcp_zone=gcp_zone,
            ssh_key_path="~/.ssh/superdeploy_deploy",
            ssh_public_key_path="~/.ssh/superdeploy_deploy.pub",
            ssh_user="superdeploy",
            docker_registry="docker.io",
            docker_organization=payload.secrets.docker_org,
            vpc_subnet="10.1.0.0/16",
            docker_subnet="172.30.0.0/24",
            vms=vms_config,
            apps_config=apps_config,
            addons_config=addons_config,
        )
        db.add(db_project)
        db.flush()

    # Create shared secrets in database
    shared_secrets = {
        "DOCKER_ORG": payload.secrets.docker_org,
        "DOCKER_USERNAME": payload.secrets.docker_username,
        "DOCKER_TOKEN": payload.secrets.docker_token,
        "REPOSITORY_TOKEN": payload.secrets.github_token,
    }

    # Add SMTP secrets if provided
    if payload.secrets.smtp_host:
        shared_secrets["SMTP_HOST"] = payload.secrets.smtp_host
        shared_secrets["SMTP_PORT"] = payload.secrets.smtp_port
        shared_secrets["SMTP_USER"] = payload.secrets.smtp_user
        shared_secrets["SMTP_PASSWORD"] = payload.secrets.smtp_password

    for key, value in shared_secrets.items():
        secret = Secret(
            project_name=payload.project_name,
            app_name=None,  # Shared secret
            key=key,
            value=value,
            environment="production",
            source="shared",
            editable=True,
        )
        db.add(secret)

    # NOTE: Addon secrets are NOT generated here
    # They will be auto-generated by CLI during first deployment (up command)
    # This keeps dashboard lightweight and follows "lazy generation" principle

    # Create apps in database
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


@router.post("/{project_name}/deploy")
async def deploy_project_wizard(project_name: str, db: Session = Depends(get_db)):
    """Deploy a project from wizard."""
    from fastapi.responses import StreamingResponse
    import asyncio
    import re

    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    def strip_ansi_codes(text: str) -> str:
        """Remove ANSI color codes from text."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    async def generate_logs():
        deployment_failed = False
        try:
            # Run CLI up command
            process = await asyncio.create_subprocess_exec(
                "superdeploy",
                f"{project_name}:up",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd="/Users/cfkarakulak/Desktop/cheapa.io/hero/superdeploy",
            )

            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode().strip()
                    if decoded_line:
                        # Strip ANSI codes
                        clean_line = strip_ansi_codes(decoded_line)
                        if clean_line:
                            yield f"data: {clean_line}\n\n"

            await process.wait()

            if process.returncode == 0:
                yield "data: ✓ Deployment complete!\n\n"
            else:
                deployment_failed = True
                yield f"data: ✗ Deployment failed (exit code: {process.returncode})\n\n"

        except Exception as e:
            deployment_failed = True
            yield f"data: ✗ Error: {str(e)}\n\n"

        # If deployment failed, keep project and secrets in database for retry
        # User can manually delete from settings page if needed
        if deployment_failed:
            yield "data: ⚠ Deployment failed - project kept in database for retry\n\n"
            yield "data: ℹ️  Fix issues and try deploying again from dashboard\n\n"

    return StreamingResponse(generate_logs(), media_type="text/event-stream")


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
