from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Project, App
from pydantic import BaseModel
import json
import subprocess

router = APIRouter(tags=["apps"])


class SwitchVersionRequest(BaseModel):
    """Request to switch to a different version."""

    git_sha: str


@router.get("/{project_name}/list")
async def list_apps(project_name: str, db: Session = Depends(get_db)):
    """
    List all apps for a project from database.

    Database is the master source, not config.yml.
    """
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
                "repo": app.repo,
                "owner": app.owner,
            }
        )

    return {"apps": apps_list}


@router.get("/{project_name}/{app_name}/releases")
async def get_releases(project_name: str, app_name: str, db: Session = Depends(get_db)):
    """
    Get deployment history (releases) for an app.
    Uses SuperDeploy CLI to read versions.json from the VM.

    Returns:
    - version: Release version
    - git_sha: Git commit SHA (full and short)
    - deployed_by: Who deployed it
    - deployed_at: When it was deployed
    - branch: Git branch
    - commit_message: Commit message (if available)
    """
    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Use backend's SSH service with proper abstraction (no direct SSH!)
        from pathlib import Path
        from services.ssh_service import SSHConnectionPool
        from services.config_service import ConfigService

        project_root = Path(__file__).parent.parent.parent.parent
        ssh_pool = SSHConnectionPool(project_root)
        config_service = ConfigService(project_root)

        try:
            # Get VM info from state
            vms = ssh_pool.get_vm_info_from_state(project_name)

            # Find which VM hosts this app
            config = config_service.read_config(project_name)
            app_config = config.get("apps", {}).get(app_name, {})
            vm_name = app_config.get("vm")

            if not vm_name or vm_name not in vms:
                return {"releases": []}

            vm_ip = vms[vm_name]["external_ip"]
            ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

            # Read releases.json via backend SSH service (not direct SSH!)
            # releases.json contains last 5 deployments for each app
            stdout, stderr, exit_code = await ssh_pool.execute_command(
                vm_ip,
                ssh_key_path,
                f"cat /opt/superdeploy/projects/{project_name}/releases.json 2>/dev/null || echo '{{}}'",
                timeout=10,
            )

            if exit_code != 0 or not stdout.strip():
                return {"releases": []}

            # Parse releases.json (array of releases)
            releases_data = json.loads(stdout)

            if app_name not in releases_data:
                return {"releases": []}

            # Get releases array for this app (last 5)
            app_releases = releases_data[app_name]

            if not isinstance(app_releases, list) or len(app_releases) == 0:
                return {"releases": []}

            # Format releases (newest first)
            formatted_releases = []
            for idx, release_data in enumerate(reversed(app_releases)):
                git_sha = release_data.get("git_sha", "-")

                # First one is CURRENT, rest are PREVIOUS
                status = (
                    "CURRENT"
                    if idx == 0
                    else f"PREVIOUS (v{release_data.get('version', '-')})"
                )

                formatted_releases.append(
                    {
                        "version": release_data.get("version", "-"),
                        "git_sha": git_sha,
                        "deployed_by": release_data.get("deployed_by", "-"),
                        "deployed_at": release_data.get("deployed_at", "-"),
                        "branch": release_data.get("branch", "-"),
                        "commit_message": release_data.get("commit_message", "-"),
                        "status": status,
                    }
                )

            return {"releases": formatted_releases}

        finally:
            await ssh_pool.close_all()

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid versions data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/{app_name}/switch")
async def switch_version(
    project_name: str,
    app_name: str,
    request: SwitchVersionRequest,
    db: Session = Depends(get_db),
):
    """
    Switch app to a different version (rollback/rollforward).
    Uses SuperDeploy CLI switch command for zero-downtime deployment.

    Returns:
    - message: Success/failure message
    - git_sha: Version switched to
    """
    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Use SuperDeploy CLI switch command (handles all SSH internally)
        result = subprocess.run(
            [
                "superdeploy",
                f"{project_name}:releases:switch",
                "-a",
                app_name,
                "-v",
                request.git_sha,
                "--force",  # Skip confirmation
            ],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes for zero-downtime switch
        )

        if result.returncode != 0:
            # Parse error from CLI output
            error_msg = result.stderr or result.stdout or "Switch failed"
            raise HTTPException(status_code=500, detail=error_msg)

        return {
            "message": f"Successfully switched to {request.git_sha[:7]}",
            "git_sha": request.git_sha,
            "output": result.stdout,
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Switch operation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
