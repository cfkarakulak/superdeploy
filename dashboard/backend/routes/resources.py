"""Application resources (processes & add-ons) routes - Heroku-like."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import App, Secret, Project, VM, Addon, Process

router = APIRouter(tags=["resources"])


class RotateCredentialRequest(BaseModel):
    credential_key: str


def _get_addon_credentials_from_db(
    project_id: int,
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
                Secret.project_id == project_id,
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

    Reads from database - use sync endpoint to refresh from live VMs.

    Returns:
        {
            "formation": [...],  # Process definitions
            "addons": [...],     # Attached addons
            "app_info": {...}    # App metadata
        }
    """
    try:
        # Get project from database
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_name}' not found"
            )

        # Get app from database
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )

        if not app:
            raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")

        # Get VM for this app
        vm = (
            db.query(VM)
            .filter(VM.project_id == project.id, VM.role == (app.vm or "app"))
            .first()
        )

        # ================================================================
        # FORMATION - Get from processes table (DB-based)
        # ================================================================
        formation = []
        processes = db.query(Process).filter(Process.app_id == app.id).all()

        if processes:
            for proc in processes:
                formation.append(
                    {
                        "name": proc.name,
                        "command": proc.command or "",
                        "replicas": proc.replicas or 1,
                        "port": proc.port,
                        "run_on": app.vm or "app",
                    }
                )
        else:
            # Fallback: show default web process if no processes in DB
            formation.append(
                {
                    "name": "web",
                    "command": "",
                    "replicas": 1,
                    "port": app.port or 8000,
                    "run_on": app.vm or "app",
                }
            )

        # ================================================================
        # ADD-ONS - Get from addons table with real-time status
        # ================================================================
        addons_response = []
        addons = db.query(Addon).filter(Addon.project_id == project.id).all()

        # Get real-time container status from CLI
        addon_statuses = {}
        try:
            from utils.cli import get_cli

            cli = get_cli()
            status_data = await cli.execute_json(
                f"{project_name}:status", args=["-a", app_name]
            )
            app_status = status_data.get("app_status", {})
            cli_addons = app_status.get("addons", [])

            # Build status map
            for cli_addon in cli_addons:
                addon_ref = cli_addon.get("reference", "")
                addon_statuses[addon_ref] = cli_addon.get("status", "attached")
        except Exception:
            # If CLI fails, all addons default to "attached" status
            pass

        for addon in addons:
            addon_ref = f"{addon.category}.{addon.instance_name}"
            status = addon_statuses.get(addon_ref, "attached")

            addons_response.append(
                {
                    "name": addon.instance_name,
                    "type": addon.type,
                    "category": addon.category,
                    "full_name": addon_ref,
                    "reference": addon_ref,  # Add reference field for frontend compatibility
                    "version": addon.version or "latest",
                    "plan": addon.plan or "standard",
                    "status": status,
                }
            )

        # ================================================================
        # APP INFO - From database
        # ================================================================
        app_info = {
            "name": app_name,
            "type": app.type or "web",
            "port": app.port or 8000,
            "vm": app.vm or "app",
            "vm_name": vm.name if vm else None,
            "vm_ip": vm.external_ip if vm else None,
            "replicas": 1,
            "repo": app.repo,
            "owner": app.owner,
        }

        return {
            "formation": formation,
            "addons": addons_response,
            "app_info": app_info,
        }

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

    Args:
        project_name: Name of the project
        app_name: Name of the app
        addon_ref: Addon reference (e.g., "databases.primary" or "queues.primary")

    Returns:
        Addon details with credentials (environment variables)
    """
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
        # Get addon from database (primary source)
        # ================================================================
        # Get addon from addons table
        addon_record = (
            db.query(Addon)
            .filter(
                Addon.project_id == project.id,
                Addon.category == category,
                Addon.instance_name == name,
            )
            .first()
        )

        if not addon_record:
            raise HTTPException(
                status_code=404, detail=f"Addon '{addon_ref}' not found in database"
            )

        # Build addon detail from DB
        addon_type = addon_record.type
        addon_name = addon_record.instance_name

        addon_detail = {
            "reference": addon_ref,
            "name": addon_name,
            "type": addon_type,
            "category": category,
            "version": addon_record.version or "latest",
            "plan": addon_record.plan or "standard",
            "as_prefix": addon_type.upper(),
            "access": "attached",
            "status": "up",  # Default, will be updated from CLI if available
            "container_name": f"{project_name}_{addon_type}_{addon_name}",
        }

        # Get real-time status from CLI if available
        try:
            from utils.cli import get_cli

            cli = get_cli()
            status_data = await cli.execute_json(
                f"{project_name}:status", args=["-a", app_name]
            )
            app_status = status_data.get("app_status", {})
            cli_addons = app_status.get("addons", [])

            # Find this addon in CLI response
            for cli_addon in cli_addons:
                if cli_addon.get("reference") == addon_ref:
                    addon_detail["status"] = cli_addon.get("status", "up")
                    break
        except Exception as e:
            # If CLI fails, keep default status
            print(f"Warning: Failed to get CLI status: {e}")

        # Get credentials from database
        credentials_dict = _get_addon_credentials_from_db(
            project.id, addon_type, addon_name, db
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

        return {"addon": addon_detail}

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
