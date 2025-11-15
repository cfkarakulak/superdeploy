"""Application resources (processes & add-ons) routes - Heroku-like."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import App, Addon
from utils.cli import get_cli

router = APIRouter(tags=["resources"])


@router.get("/{project_name}/{app_name}")
async def get_app_resources(
    project_name: str, app_name: str, db: Session = Depends(get_db)
):
    """
    Get application resources: process formation and attached add-ons.

    Uses CLI JSON output to get real-time status from VMs.

    Returns:
        {
            "formation": [...],  # Process definitions
            "addons": [...],     # Attached addons with real status
            "app_info": {...}    # App metadata
        }
    """
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
        # FORMATION - Process definitions from marker file (via ps command)
        # ================================================================
        formation = []

        # Get process definitions from ps command (reads from marker file)
        try:
            ps_data = await cli.execute_json(f"{project_name}:ps")
            apps_data = ps_data.get("apps", [])

            # Find our app in the ps output
            for app_data in apps_data:
                if app_data.get("name") == app_name:
                    # Get processes from marker file
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

        # Fallback to DB if no processes found
        if not formation:
            processes = app.processes or {}
            for process_name, process_config in processes.items():
                formation.append(
                    {
                        "name": process_name,
                        "command": process_config.get("command", ""),
                        "replicas": process_config.get("replicas", 1),
                        "port": process_config.get("port"),
                        "run_on": process_config.get("run_on"),
                    }
                )

        # ================================================================
        # ADD-ONS - Get from CLI status (includes real runtime status)
        # ================================================================
        addons_response = app_status.get("addons", [])

        # If no addons from CLI, fallback to DB (legacy)
        if not addons_response:
            all_addons = db.query(Addon).filter(Addon.project_id == project.id).all()

            for addon in all_addons:
                # Check if this addon is attached to our app
                attachments = addon.attachments or []

                matching_attachment = None
                for att in attachments:
                    if att.get("app_name") == app_name:
                        matching_attachment = att
                        break

                if not matching_attachment:
                    continue

                # This addon is attached to our app
                as_prefix = matching_attachment.get("as_prefix", addon.type.upper())
                access = matching_attachment.get("access", "readwrite")

                # Get credentials
                credentials = addon.credentials or {}

                # Build reference (category.name format)
                reference = f"{addon.category}.{addon.name}"

                addons_response.append(
                    {
                        "reference": reference,
                        "name": addon.name,
                        "type": addon.type,
                        "category": addon.category,
                        "version": addon.version or "",
                        "plan": addon.plan,
                        "as_prefix": as_prefix,
                        "access": access,
                        "status": addon.status,
                        "host": credentials.get("HOST", ""),
                        "port": credentials.get("PORT", ""),
                        "container_name": f"{project_name}_{addon.type}_{addon.name}",
                        "source": "db",
                    }
                )

        # ================================================================
        # APP INFO - From CLI status
        # ================================================================
        app_info = {
            "name": app_name,
            "type": app_status.get("type", app.type or "web"),
            "port": app_status.get("port", app.port),
            "vm": app_status.get("vm", app.vm or "app"),
            "vm_name": app_status.get("vm_name"),
            "vm_ip": app_status.get("vm_ip"),
            "replicas": app_status.get("replicas", 1),
            "deployment": app_status.get("deployment", {}),
            "processes": app_status.get("processes", []),
            "resources": app_status.get("resources", {}),
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

        # Get addon
        addon = (
            db.query(Addon)
            .filter(
                Addon.project_id == project.id,
                Addon.category == category,
                Addon.name == name,
            )
            .first()
        )

        if not addon:
            raise HTTPException(
                status_code=404, detail=f"Addon '{addon_ref}' not found"
            )

        # Check if addon is attached to this app
        attachments = addon.attachments or []
        matching_attachment = None

        for att in attachments:
            if att.get("app_name") == app_name:
                matching_attachment = att
                break

        if not matching_attachment:
            raise HTTPException(
                status_code=404,
                detail=f"Addon '{addon_ref}' is not attached to app '{app_name}'",
            )

        # Get attachment details
        as_prefix = matching_attachment.get("as_prefix", addon.type.upper())
        access = matching_attachment.get("access", "readwrite")

        # Get credentials and format them as environment variables
        credentials_dict = addon.credentials or {}
        credentials_list = []

        for key, value in credentials_dict.items():
            # Format as environment variable with prefix
            env_key = f"{as_prefix}_{key}"
            credentials_list.append({"key": env_key, "value": str(value)})

        # Build response
        addon_detail = {
            "reference": addon_ref,
            "name": addon.name,
            "type": addon.type,
            "category": addon.category,
            "version": addon.version or "",
            "plan": addon.plan,
            "as_prefix": as_prefix,
            "access": access,
            "status": addon.status,
            "host": credentials_dict.get("HOST", ""),
            "port": credentials_dict.get("PORT", ""),
            "container_name": f"{project_name}_{addon.type}_{addon.name}",
            "credentials": credentials_list,
        }

        return {"addon": addon_detail}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
