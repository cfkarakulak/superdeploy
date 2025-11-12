"""Application management and scaling routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

router = APIRouter(tags=["apps"])

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class ScaleRequest(BaseModel):
    """Request to scale app processes."""

    process_type: str
    replicas: int


class DeployRequest(BaseModel):
    """Request to trigger deployment."""

    branch: Optional[str] = "production"


@router.get("/{project_name}/list")
async def list_apps(project_name: str):
    """
    List all apps for a project from database.

    Database is the master source, not config.yml.
    """
    from dashboard.backend.database import SessionLocal
    from dashboard.backend.models import Project, App

    db = SessionLocal()

    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get apps from DB
        apps = db.query(App).filter(App.project_id == project.id).all()

        apps_list = []
        for app in apps:
            apps_list.append(
                {
                    "name": app.name,
                    "type": app.type,
                    "domain": app.domain,
                    "vm": app.vm,
                    "port": app.port,
                }
            )

        return {"apps": apps_list}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{project_name}/apps/{app_name}/scale")
async def scale_app(project_name: str, app_name: str, request: ScaleRequest):
    """
    Scale an app's process replicas.

    Updates docker-compose.yml and scales containers.
    """
    from dashboard.backend.services.config_service import ConfigService
    from dashboard.backend.services.ssh_service import SSHConnectionPool

    config_service = ConfigService(PROJECT_ROOT)
    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Read config to get current replica count
        config = config_service.read_config(project_name)
        apps_config = config.get("apps", {})

        if app_name not in apps_config:
            raise HTTPException(status_code=404, detail=f"App {app_name} not found")

        app_config = apps_config[app_name]
        processes = app_config.get("processes", {})

        if request.process_type not in processes:
            raise HTTPException(
                status_code=404,
                detail=f"Process {request.process_type} not found in app {app_name}",
            )

        # Get old replica count
        old_replicas = processes[request.process_type].get("replicas", 1)

        # Update config
        processes[request.process_type]["replicas"] = request.replicas
        config_service.write_config(project_name, config)

        # Get VM info
        vm_name = app_config.get("vm")
        vms = ssh_pool.get_vm_info_from_state(project_name)

        if vm_name not in vms:
            raise HTTPException(status_code=404, detail=f"VM {vm_name} not found")

        vm_ip = vms[vm_name].get("external_ip")
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        # Scale using docker compose
        compose_dir = f"/opt/superdeploy/projects/{project_name}/compose"
        service_name = f"{app_name}-{request.process_type}"

        scale_command = (
            f"cd {compose_dir} && "
            f"docker compose up -d --scale {service_name}={request.replicas} --no-recreate"
        )

        stdout, stderr, exit_code = await ssh_pool.execute_command(
            vm_ip, ssh_key_path, scale_command, timeout=60
        )

        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to scale: {stderr}")

        return {
            "success": True,
            "message": f"Scaled {app_name}:{request.process_type} from {old_replicas} to {request.replicas} replicas",
            "app_name": app_name,
            "process_type": request.process_type,
            "old_replicas": old_replicas,
            "new_replicas": request.replicas,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()


@router.post("/{project_name}/apps/{app_name}/deploy")
async def deploy_app(project_name: str, app_name: str, request: DeployRequest):
    """
    Trigger deployment for an app via GitHub Actions.

    Uses GitHub API to trigger workflow dispatch.
    """
    from dashboard.backend.services.config_service import ConfigService
    import httpx

    config_service = ConfigService(PROJECT_ROOT)

    try:
        # Read config to get GitHub org
        config = config_service.read_config(project_name)
        github_org = config.get("github", {}).get("organization")

        if not github_org:
            raise HTTPException(
                status_code=400, detail="GitHub organization not configured"
            )

        # Read secrets to get GitHub token
        secrets = config_service.read_secrets(project_name)
        github_token = secrets.get("secrets", {}).get("shared", {}).get("GITHUB_TOKEN")

        if not github_token:
            raise HTTPException(
                status_code=400, detail="GitHub token not found in secrets"
            )

        # Trigger workflow via GitHub API
        repo_name = app_name  # Assume repo name matches app name
        workflow_file = "deploy.yml"

        url = f"https://api.github.com/repos/{github_org}/{repo_name}/actions/workflows/{workflow_file}/dispatches"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"ref": request.branch},
            )

            if response.status_code not in [204, 200]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

        return {
            "success": True,
            "message": f"Deployment triggered for {app_name} from {request.branch} branch",
            "app_name": app_name,
            "branch": request.branch,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/apps/{app_name}/deployments")
async def get_deployment_history(project_name: str, app_name: str, limit: int = 10):
    """
    Get deployment history for an app.

    Reads versions.json from VM and optionally GitHub Actions history.
    """
    from dashboard.backend.services.ssh_service import SSHConnectionPool
    from dashboard.backend.services.config_service import ConfigService
    import json

    ssh_pool = SSHConnectionPool(PROJECT_ROOT)
    config_service = ConfigService(PROJECT_ROOT)

    try:
        # Get config
        config = config_service.read_config(project_name)
        apps_config = config.get("apps", {})

        if app_name not in apps_config:
            raise HTTPException(status_code=404, detail=f"App {app_name} not found")

        app_config = apps_config[app_name]
        vm_name = app_config.get("vm")

        # Get VM info
        vms = ssh_pool.get_vm_info_from_state(project_name)

        if vm_name not in vms:
            raise HTTPException(status_code=404, detail=f"VM {vm_name} not found")

        vm_ip = vms[vm_name].get("external_ip")
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        # Read versions.json from VM
        versions_file = f"/opt/superdeploy/projects/{project_name}/versions.json"
        read_command = f"cat {versions_file}"

        stdout, stderr, exit_code = await ssh_pool.execute_command(
            vm_ip, ssh_key_path, read_command
        )

        if exit_code != 0:
            # versions.json doesn't exist yet
            return {"deployments": [], "current_version": None}

        try:
            versions_data = json.loads(stdout)
            app_version = versions_data.get(app_name, {})

            # For now, return single deployment (current)
            # TODO: Track full history in database
            deployments = []
            if app_version:
                deployments.append(
                    {
                        "version": app_version.get("version"),
                        "git_sha": app_version.get("git_sha"),
                        "branch": app_version.get("branch"),
                        "deployed_at": app_version.get("deployed_at"),
                        "deployed_by": app_version.get("deployed_by"),
                        "status": "success",
                        "current": True,
                    }
                )

            return {
                "deployments": deployments[:limit],
                "current_version": app_version.get("version"),
            }

        except json.JSONDecodeError:
            return {"deployments": [], "current_version": None}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()


@router.post("/{project_name}/apps/{app_name}/rollback")
async def rollback_app(project_name: str, app_name: str, target_version: str):
    """
    Rollback app to a previous version.

    Re-runs GitHub Actions deployment for that version.
    """
    # TODO: Implement using GitHub Actions re-run
    # Need to find workflow run for that version and re-run it

    raise HTTPException(
        status_code=501,
        detail="Rollback not yet implemented. Use GitHub Actions UI to re-run previous successful deployment.",
    )
