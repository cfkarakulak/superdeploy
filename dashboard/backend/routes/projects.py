from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
from database import get_db
from models import Project, App, VM, Addon, Secret

# Get superdeploy root directory (dashboard/backend/routes -> superdeploy root)
SUPERDEPLOY_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

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


class AppResponse(BaseModel):
    id: int
    name: str
    repo: Optional[str] = None
    owner: Optional[str] = None
    type: Optional[str] = None
    vm: Optional[str] = None
    port: Optional[int] = None
    internal_port: Optional[int] = None
    external_port: Optional[int] = None
    path: Optional[str] = None
    services: Optional[dict] = None

    class Config:
        from_attributes = True


class AddonResponse(BaseModel):
    id: int
    instance_name: str
    category: str
    type: str
    version: Optional[str] = None
    vm: Optional[str] = None
    plan: Optional[str] = None

    class Config:
        from_attributes = True


class VMResponse(BaseModel):
    id: int
    role: str
    count: Optional[int] = 1
    machine_type: Optional[str] = "e2-medium"
    disk_size: Optional[int] = 20

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    project_type: Optional[str] = "application"
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
    apps: List[AppResponse] = []
    addons: List[AddonResponse] = []
    vms: List[VMResponse] = []

    class Config:
        from_attributes = True


class OrchestratorResponse(BaseModel):
    """Response for orchestrator status."""

    id: int
    name: str
    project_type: str
    gcp_project: Optional[str] = None
    gcp_region: Optional[str] = None
    deployed: bool = False
    ip: Optional[str] = None
    grafana_url: Optional[str] = None
    prometheus_url: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all application projects from database (excludes orchestrator)."""
    projects = db.query(Project).filter(Project.project_type == "application").all()
    return projects


@router.get("/orchestrator", response_model=OrchestratorResponse)
def get_orchestrator(db: Session = Depends(get_db)):
    """Get orchestrator status and access info."""
    orchestrator = (
        db.query(Project).filter(Project.project_type == "orchestrator").first()
    )
    if not orchestrator:
        raise HTTPException(status_code=404, detail="Orchestrator not configured")

    # Get orchestrator IP from secrets or VMs table
    ip = None
    deployed = False

    # Try secrets first (ORCHESTRATOR_IP)
    from models import Secret, VM

    secret = (
        db.query(Secret)
        .filter(Secret.project_id == orchestrator.id, Secret.key == "ORCHESTRATOR_IP")
        .first()
    )
    if secret:
        ip = secret.value
        deployed = True

    # Fallback to VMs table
    if not ip:
        vm = (
            db.query(VM)
            .filter(VM.project_id == orchestrator.id, VM.external_ip.isnot(None))
            .first()
        )
        if vm:
            ip = vm.external_ip
            deployed = True

    return {
        "id": orchestrator.id,
        "name": orchestrator.name,
        "project_type": orchestrator.project_type,
        "gcp_project": orchestrator.gcp_project,
        "gcp_region": orchestrator.gcp_region,
        "deployed": deployed,
        "ip": ip,
        "grafana_url": f"http://{ip}:3000" if ip else None,
        "prometheus_url": f"http://{ip}:9090" if ip else None,
    }


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


@router.get("/{project_name}/deployment-history")
async def get_deployment_history(project_name: str, db: Session = Depends(get_db)):
    """Get recent deployment history for all apps in project."""
    from models import DeploymentHistory
    from sqlalchemy import desc, text

    # Get project
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get recent deployments (last 50)
    deployments = (
        db.query(DeploymentHistory)
        .filter(DeploymentHistory.project_id == project.id)
        .order_by(desc(DeploymentHistory.deployed_at))
        .limit(50)
        .all()
    )

    # Count total and deployed apps
    apps = db.query(App).filter(App.project_id == project.id).all()
    total_apps = len(apps)

    # Count deployed apps by checking running containers
    deployed_apps = 0
    try:
        # Get all apps
        app_names = [app.name for app in apps]

        # Check if containers exist for each app
        from cli.services.vm_service import VMService
        from cli.services.config_service import ConfigService
        from pathlib import Path

        # Get VM service - project root is parent of dashboard directory
        dashboard_dir = Path(
            __file__
        ).parent.parent.parent  # dashboard/backend/routes -> dashboard
        project_root = dashboard_dir.parent  # dashboard -> superdeploy
        config_service = ConfigService(project_root)
        vm_service = VMService(project_name, config_service)
        ssh_service = vm_service.get_ssh_service()

        # Get all VMs
        all_vms = vm_service.get_all_vms()
        running_apps = set()

        # Check containers on each VM
        for vm_name, vm_data in all_vms.items():
            vm_ip = vm_data.get("external_ip")
            if not vm_ip:
                continue

            try:
                # Get running containers
                result = ssh_service.execute_command(
                    vm_ip,
                    "docker ps --format '{{.Names}}'",
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout.strip():
                    for container_name in result.stdout.strip().split("\n"):
                        if not container_name:
                            continue
                        # Check if it's an app container (compose-{app}-{process}-{replica})
                        if container_name.startswith("compose-"):
                            parts = container_name.split("-")
                            if len(parts) >= 3:
                                app_name = parts[1]
                                if app_name in app_names:
                                    running_apps.add(app_name)
            except Exception:
                # Skip if SSH fails
                continue

        deployed_apps = len(running_apps) if running_apps else 0
    except Exception as e:
        print(f"Warning: Failed to check deployed apps via containers: {e}")
        # Fallback: assume all apps are deployed if we have containers running
        # Check if any containers exist at all
        try:
            from cli.services.vm_service import VMService
            from cli.services.config_service import ConfigService
            from pathlib import Path

            # Get VM service - project root is parent of dashboard directory
            dashboard_dir = Path(
                __file__
            ).parent.parent.parent  # dashboard/backend/routes -> dashboard
            project_root = dashboard_dir.parent  # dashboard -> superdeploy
            config_service = ConfigService(project_root)
            vm_service = VMService(project_name, config_service)
            ssh_service = vm_service.get_ssh_service()
            all_vms = vm_service.get_all_vms()

            has_containers = False
            for vm_name, vm_data in all_vms.items():
                vm_ip = vm_data.get("external_ip")
                if vm_ip:
                    try:
                        result = ssh_service.execute_command(
                            vm_ip,
                            "docker ps --format '{{.Names}}' | head -1",
                            timeout=3,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            has_containers = True
                            break
                    except:
                        pass

            # If containers exist, assume apps are deployed
            if has_containers:
                deployed_apps = total_apps
            else:
                deployed_apps = 0
        except:
            # Final fallback: count apps with successful deployments
            deployed_apps_result = db.execute(
                text("""
                    SELECT COUNT(DISTINCT app_name)
                    FROM deployment_history
                    WHERE project_id = :project_id
                    AND status = 'success'
                """),
                {"project_id": project.id},
            )
            deployed_apps = deployed_apps_result.scalar() or 0

    # Get last deployment time
    last_deployment = None
    if deployments:
        last_deployment = (
            deployments[0].deployed_at.isoformat()
            if deployments[0].deployed_at
            else None
        )

    deployment_list = []
    for d in deployments:
        deployment_list.append(
            {
                "app_name": d.app_name,
                "version": d.version,
                "git_sha": d.git_sha[:7] if d.git_sha else "-",
                "branch": d.branch or "-",
                "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
                "deployed_by": d.deployed_by or "system",
                "status": d.status,
                "duration": d.duration,
            }
        )

    return {
        "stats": {
            "total_apps": total_apps,
            "deployed_apps": deployed_apps,
            "last_deployment": last_deployment,
        },
        "deployments": deployment_list,
    }


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
        current_line_buffer = ""

        try:
            # Run CLI down command with --yes flag
            process = await asyncio.create_subprocess_exec(
                "superdeploy",
                f"{project_name}:down",
                "--yes",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(SUPERDEPLOY_ROOT),
            )

            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode()

                    # Handle carriage returns - split by \r and take last part
                    if "\r" in decoded_line:
                        parts = decoded_line.split("\r")
                        # Last part is the one that should be displayed
                        decoded_line = parts[-1]

                    decoded_line = decoded_line.strip()
                    if decoded_line:
                        # Strip ANSI codes
                        clean_line = strip_ansi_codes(decoded_line)
                        if clean_line:
                            yield f"data: {clean_line}\n\n"

            await process.wait()

            if process.returncode == 0:
                # Delete from database after successful teardown
                db.query(Secret).filter(Secret.project_id == project.id).delete()
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
    db.query(Secret).filter(Secret.project_id == project.id).delete()

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
        db.query(Secret).filter(Secret.project_id == existing.id).delete()
        db.flush()

    # Create App records in database
    for app in payload.apps:
        # Parse repo owner/name
        repo_parts = app.repo.split("/")
        owner = repo_parts[0] if len(repo_parts) > 0 else payload.github_org
        repo_name = repo_parts[1] if len(repo_parts) > 1 else app.repo

        # Check if app already exists
        existing_app = (
            db.query(App)
            .filter(
                App.project_id == db_project.id if existing else None,
                App.name == app.name,
            )
            .first()
        )

        if existing_app:
            # Update existing app
            existing_app.repo = app.repo
            existing_app.owner = owner
            existing_app.path = f"~/repos/{owner}/{repo_name}"
            existing_app.vm = "app"
            existing_app.port = app.port
        else:
            # Create new app
            new_app = App(
                project_id=db_project.id
                if existing
                else None,  # Will be set after project creation
                name=app.name,
                repo=app.repo,
                owner=owner,
                path=f"~/repos/{owner}/{repo_name}",
                vm="app",
                port=app.port,
            )
            db.add(new_app)

    # Create Addon records
    addons_dict = payload.addons.dict()
    addon_records = []

    # Process each addon category
    for category, addon_types in addons_dict.items():
        if addon_types:  # If category has addons selected
            for addon_type in addon_types:
                addon_records.append(
                    {
                        "name": "primary",  # First instance always named "primary"
                        "category": category,
                        "type": addon_type,
                        "version": ADDON_VERSIONS.get(addon_type, {}).get(
                            "version", "latest"
                        ),
                        "vm": ADDON_VERSIONS.get(addon_type, {}).get("vm", "core"),
                    }
                )

    # CRITICAL: Add Caddy as "primary" instance (required for app routing)
    # Even if user didn't select proxy in wizard, Caddy must be added
    has_caddy = any(
        a["category"] == "proxy" and a["type"] == "caddy" for a in addon_records
    )
    if not has_caddy:
        addon_records.append(
            {
                "name": "primary",
                "category": "proxy",
                "type": "caddy",
                "version": "2-alpine",
                "vm": "core",
            }
        )

    # Create VM records (default setup)
    vm_records = [
        {"role": "core", "count": 1, "machine_type": "e2-medium", "disk_size": 20},
        {"role": "app", "count": 1, "machine_type": "e2-medium", "disk_size": 30},
    ]

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
        db.flush()

        # Delete old VMs and Addons, create new ones
        db.query(VM).filter(VM.project_id == db_project.id).delete()
        db.query(Addon).filter(Addon.project_id == db_project.id).delete()

        # Create new VM records
        for vm_data in vm_records:
            vm = VM(project_id=db_project.id, **vm_data)
            db.add(vm)

        # Create new Addon records
        for addon_data in addon_records:
            addon = Addon(project_id=db_project.id, **addon_data)
            db.add(addon)
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
        )
        db.add(db_project)
        db.flush()

        # Update app records with project_id
        for app in db.query(App).filter(App.project_id == None).all():
            app.project_id = db_project.id

        # Create VM records
        for vm_data in vm_records:
            vm = VM(project_id=db_project.id, **vm_data)
            db.add(vm)

        # Create Addon records
        for addon_data in addon_records:
            addon = Addon(project_id=db_project.id, **addon_data)
            db.add(addon)

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
        current_line_buffer = ""

        try:
            # Run CLI up command
            process = await asyncio.create_subprocess_exec(
                "superdeploy",
                f"{project_name}:up",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(SUPERDEPLOY_ROOT),
            )

            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode()

                    # Handle carriage returns - split by \r and take last part
                    if "\r" in decoded_line:
                        parts = decoded_line.split("\r")
                        # Last part is the one that should be displayed
                        decoded_line = parts[-1]

                    decoded_line = decoded_line.strip()
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
def get_project_vms(project_name: str, db: Session = Depends(get_db)):
    """Get VMs for a project from database."""
    try:
        # Get project from database
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get VMs directly from vms table
        vms = []
        db_vms = db.query(VM).filter(VM.project_id == project.id).all()
        for vm in db_vms:
            vms.append(
                {
                    "name": vm.name or f"{project_name}-{vm.role}",
                    "role": vm.role,
                    "ip": vm.external_ip or "N/A",
                    "zone": project.gcp_zone or "N/A",
                    "machine_type": vm.machine_type or "e2-medium",
                    "status": vm.status or "unknown",
                }
            )

        # Get orchestrator IP from secrets
        orchestrator = db.query(Project).filter(Project.name == "orchestrator").first()
        orchestrator_ip = None
        if orchestrator:
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == orchestrator.id,
                    Secret.key == "ORCHESTRATOR_IP",
                )
                .first()
            )
            if secret:
                orchestrator_ip = secret.value

        response = {
            "orchestrator_ip": orchestrator_ip,
            "vms": vms,
        }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/{project_name}/sync")
async def sync_project_from_vms(project_name: str, db: Session = Depends(get_db)):
    """
    Sync project state from live VMs to database.
    Queries VM status via gcloud and container status via SSH, then updates DB.
    """
    import subprocess

    try:
        # Get project from database
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project {project_name} not found"
            )

        # Get VMs for this project
        vms = db.query(VM).filter(VM.project_id == project.id).all()
        if not vms:
            return {"status": "success", "message": "No VMs to sync", "synced": 0}

        ssh_key = project.ssh_key_path or "~/.ssh/superdeploy_deploy"
        ssh_user = project.ssh_user or "superdeploy"

        synced_count = 0
        container_count = 0

        # For each VM, get status and containers
        for vm in vms:
            vm_key = f"{vm.role}-0"
            vm_name = f"{project_name}-{vm_key}"

            # Get VM info from gcloud
            try:
                result = subprocess.run(
                    f"gcloud compute instances describe {vm_name} --zone={project.gcp_zone or 'us-central1-a'} --format='value(networkInterfaces[0].accessConfigs[0].natIP,status)' 2>/dev/null",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split()
                    external_ip = parts[0] if parts else None
                    status = parts[1].lower() if len(parts) > 1 else "unknown"

                    # Update VM in database
                    vm.external_ip = external_ip
                    vm.status = status
                    vm.name = vm_name
                    synced_count += 1

                    # Get container status via SSH
                    if external_ip and status == "running":
                        try:
                            ssh_result = subprocess.run(
                                f"ssh -i {ssh_key} -o StrictHostKeyChecking=no -o ConnectTimeout=5 {ssh_user}@{external_ip} 'docker ps --format \"{{{{.Names}}}}|{{{{.Status}}}}\"' 2>/dev/null",
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=15,
                            )

                            if ssh_result.returncode == 0:
                                for line in ssh_result.stdout.strip().split("\n"):
                                    if "|" in line:
                                        container_count += 1
                        except Exception as ssh_err:
                            print(f"SSH failed for {vm_key}: {ssh_err}")

            except Exception as e:
                print(f"Failed to sync VM {vm_key}: {e}")
                continue

        # Commit changes to database
        db.commit()

        return {
            "status": "success",
            "message": f"Synced {synced_count} VM(s), {container_count} container(s) to database",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
