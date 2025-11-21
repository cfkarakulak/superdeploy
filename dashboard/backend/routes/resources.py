"""Application resources (processes & add-ons) routes - Heroku-like."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import App, Secret
from utils.cli import get_cli
from cache import get_cache, set_cache, CACHE_TTL

router = APIRouter(tags=["resources"])


class RotateCredentialRequest(BaseModel):
    credential_key: str


def _get_addon_credentials_from_db(
    project_name: str,
    addon_type: str,
    addon_name: str,
    db: Session,
    environment: str = "production",
) -> dict:
    """Read addon credentials from database."""
    try:
        # Query addon secrets from database
        # Format: {addon_type}.{addon_name}.{key}
        prefix = f"{addon_type}.{addon_name}."

        addon_secrets = (
            db.query(Secret)
            .filter(
                Secret.project_name == project_name,
                Secret.key.like(f"{prefix}%"),
                Secret.source == "addon",
                Secret.environment == environment,
            )
            .all()
        )

        # Convert to dict: {KEY: value}
        credentials_dict = {}
        for secret in addon_secrets:
            # Remove prefix: "postgres.primary.HOST" -> "HOST"
            key = secret.key.replace(prefix, "")
            credentials_dict[key] = secret.value

        return credentials_dict
    except Exception as e:
        print(f"Warning: Failed to read addon secrets from DB: {e}")
        return {}


@router.get("/{project_name}/{app_name}")
async def get_app_resources(
    project_name: str, app_name: str, db: Session = Depends(get_db)
):
    """
    Get application resources: process formation and attached add-ons.

    Uses CLI JSON output to get real-time status from VMs.
    Cached for 1 minute.

    Returns:
        {
            "formation": [...],  # Process definitions
            "addons": [...],     # Attached addons with real status
            "app_info": {...}    # App metadata
        }
    """
    # Check cache
    cache_key = f"resources:{project_name}:{app_name}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Get app from database
        from models import Project

        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_name}' not found"
            )

        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )

        if not app:
            raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")

        # ================================================================
        # Get real-time app status from CLI
        # ================================================================
        cli = get_cli()
        try:
            status_data = await cli.execute_json(
                f"{project_name}:status", args=["-a", app_name]
            )
            app_status = status_data.get("app_status", {})
        except Exception as e:
            # Fallback if CLI fails
            print(f"Warning: Failed to get CLI status: {e}")
            app_status = {}

        # ================================================================
        # FORMATION - Only show if app is deployed (has running processes)
        # ================================================================
        formation = []

        # Only show formation if app has running processes (is deployed)
        # This ensures we don't show config-based process definitions for non-deployed apps
        running_processes = app_status.get("processes", [])

        if running_processes:
            # App is deployed, get process definitions from config
            try:
                ps_data = await cli.execute_json(f"{project_name}:ps")
                apps_data = ps_data.get("apps", [])

                # Find our app in the ps output
                for app_data in apps_data:
                    if app_data.get("name") == app_name:
                        # Get processes from config
                        processes_dict = app_data.get("processes", {})

                        for process_name, process_config in processes_dict.items():
                            formation.append(
                                {
                                    "name": process_name,
                                    "command": process_config.get("command", ""),
                                    "replicas": process_config.get("replicas", 1),
                                    "port": process_config.get("port"),
                                    "run_on": process_config.get("run_on"),
                                }
                            )
                        break
            except Exception as e:
                print(f"Warning: Failed to get process formation from ps command: {e}")
                # If ps command fails, formation will be empty

        # ================================================================
        # ADD-ONS - Get from CLI status (includes real runtime status)
        # ================================================================
        addons_response = app_status.get("addons", [])

        # ================================================================
        # APP INFO - From CLI status
        # ================================================================
        app_info = {
            "name": app_name,
            "type": app_status.get("type", "web"),
            "port": app_status.get("port", 8000),
            "vm": app_status.get("vm", "app"),
            "vm_name": app_status.get("vm_name"),
            "vm_ip": app_status.get("vm_ip"),
            "replicas": app_status.get("replicas", 1),
            "deployment": app_status.get("deployment", {}),
            "processes": app_status.get("processes", []),
            "resources": app_status.get("resources", {}),
        }

        response = {
            "formation": formation,
            "addons": addons_response,
            "app_info": app_info,
        }

        # Cache for 1 minute
        set_cache(cache_key, response, CACHE_TTL["status"])
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/{app_name}/addon/{addon_ref:path}")
async def get_addon_detail(
    project_name: str, app_name: str, addon_ref: str, db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific addon attached to an app.
    Cached for 1 minute.

    Args:
        project_name: Name of the project
        app_name: Name of the app
        addon_ref: Addon reference (e.g., "databases.primary" or "queues.primary")

    Returns:
        Addon details with credentials (environment variables)
    """
    # Check cache
    cache_key = f"addon_detail:{project_name}:{app_name}:{addon_ref}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Parse addon_ref (format: "category.name")
        parts = addon_ref.split(".")
        if len(parts) != 2:
            raise HTTPException(
                status_code=400, detail=f"Invalid addon reference format: {addon_ref}"
            )

        category, name = parts

        # Get project
        from models import Project

        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_name}' not found"
            )

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )

        if not app:
            raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")

        # ================================================================
        # Get real-time app status from CLI (includes runtime-detected addons)
        # ================================================================
        cli = get_cli()
        try:
            status_data = await cli.execute_json(
                f"{project_name}:status", args=["-a", app_name]
            )
            app_status = status_data.get("app_status", {})
            cli_addons = app_status.get("addons", [])
        except Exception as e:
            print(f"Warning: Failed to get CLI status: {e}")
            cli_addons = []

        # Try to find addon in CLI response first (includes auto-detected addons)
        addon_data = None
        for addon_item in cli_addons:
            if addon_item.get("reference") == addon_ref:
                addon_data = addon_item
                break

        # If found in CLI
        if addon_data:
            # Build base response from CLI data
            addon_detail = {
                "reference": addon_data.get("reference"),
                "name": addon_data.get("name"),
                "type": addon_data.get("type"),
                "category": addon_data.get("category"),
                "version": addon_data.get("version", ""),
                "plan": addon_data.get("plan", "standard"),
                "as_prefix": addon_data.get("as", addon_data.get("type", "").upper()),
                "access": addon_data.get("access", "auto-detected"),
                "status": addon_data.get("status", ""),
                "container_name": f"{project_name}_{addon_data.get('type')}_{addon_data.get('name')}",
            }

            # Get credentials from database
            addon_type = addon_data.get("type")
            addon_name = addon_data.get("name")
            credentials_dict = _get_addon_credentials_from_db(
                project_name, addon_type, addon_name, db
            )

            if credentials_dict:
                credentials_list = []
                as_prefix = addon_detail["as_prefix"]

                for key, value in credentials_dict.items():
                    env_key = f"{as_prefix}_{key}"
                    credentials_list.append({"key": env_key, "value": str(value)})

                addon_detail["credentials"] = credentials_list
                addon_detail["host"] = credentials_dict.get("HOST", "")
                addon_detail["port"] = str(credentials_dict.get("PORT", ""))
            else:
                addon_detail["credentials"] = []
                addon_detail["host"] = ""
                addon_detail["port"] = ""

        else:
            # Addon not found anywhere
            raise HTTPException(
                status_code=404, detail=f"Addon '{addon_ref}' not found"
            )

        response = {"addon": addon_detail}

        # Cache for 1 minute
        set_cache(cache_key, response, CACHE_TTL["status"])
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/{app_name}/addon/{addon_ref:path}/rotate")
async def rotate_addon_credential(
    project_name: str,
    app_name: str,
    addon_ref: str,
    request: RotateCredentialRequest,
    db: Session = Depends(get_db),
):
    """
    Rotate a specific credential for an addon.

    This will:
    1. Generate a new credential value
    2. Update the addon configuration
    3. Restart the addon container
    4. Update the secret in database
    5. Trigger app deployment with new env vars

    Args:
        project_name: Name of the project
        app_name: Name of the app
        addon_ref: Addon reference (e.g., "postgres.primary")
        request: Request body with credential_key to rotate

    Returns:
        Success message with new credential info
    """
    try:
        # Parse addon_ref
        parts = addon_ref.split(".")
        if len(parts) != 2:
            raise HTTPException(
                status_code=400, detail=f"Invalid addon reference format: {addon_ref}"
            )

        addon_type, addon_name = parts

        # Verify project and app exist
        from models import Project

        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_name}' not found"
            )

        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )

        if not app:
            raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")

        # Call CLI command to rotate credential
        cli = get_cli()
        try:
            # Execute rotation command
            # Format: superdeploy project:addons:rotate TYPE NAME CREDENTIAL
            # Example: superdeploy cheapa:addons:rotate postgres primary PASSWORD

            # Extract credential name from key (e.g., "POSTGRES_PRIMARY_PASSWORD" -> "PASSWORD")
            credential_name = request.credential_key.split("_")[-1]

            rotate_result = await cli.execute_json(
                f"{project_name}:addons:rotate",
                args=[addon_type, addon_name, credential_name],
            )

            # Clear cache for this addon
            cache_key = f"addon_detail:{project_name}:{app_name}:{addon_ref}"
            from cache import delete_cache

            delete_cache(cache_key)

            # Also clear resources cache
            resources_cache_key = f"resources:{project_name}:{app_name}"
            delete_cache(resources_cache_key)

            return {
                "success": True,
                "message": f"Credential '{request.credential_key}' rotated successfully",
                "addon_ref": addon_ref,
                "credential": credential_name,
            }

        except Exception as cli_error:
            # If CLI command fails, provide helpful error
            error_msg = str(cli_error)
            if "not found" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail=f"Addon '{addon_ref}' or credential '{request.credential_key}' not found",
                )
            elif "not implemented" in error_msg.lower():
                raise HTTPException(
                    status_code=501,
                    detail=f"Credential rotation not yet implemented for {addon_type}",
                )
            else:
                raise HTTPException(
                    status_code=500, detail=f"Failed to rotate credential: {error_msg}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
