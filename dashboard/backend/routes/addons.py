from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import yaml

router = APIRouter(tags=["addons"])
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class AddonProvisionRequest(BaseModel):
    """Request to provision a new addon."""

    addon_type: str  # e.g., "postgres", "redis", "rabbitmq"
    name: str  # Unique name for this addon instance
    plan: str  # e.g., "small", "standard", "large", "xlarge"


class AddonAttachRequest(BaseModel):
    """Request to attach addon to app."""

    app_name: str
    as_prefix: Optional[str] = None  # Custom env var prefix


@router.get("/{project_name}/list")
async def list_addons(project_name: str):
    """
    List all provisioned addons for a project from database.

    Database is the master source, not config.yml.
    """
    from dashboard.backend.database import SessionLocal
    from dashboard.backend.models import Project, Addon

    db = SessionLocal()

    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get addons from DB
        addons = db.query(Addon).filter(Addon.project_id == project.id).all()

        addons_list = []
        for addon in addons:
            addons_list.append(
                {
                    "name": addon.name,
                    "type": addon.type,
                    "category": addon.category,
                    "plan": addon.plan,
                    "reference": f"{addon.category}.{addon.name}",
                    "attachments": addon.attachments or [],
                    "status": addon.status,
                }
            )

        return {"addons": addons_list}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{project_name}/marketplace")
async def get_addon_marketplace(project_name: str):
    """
    Get available addons from marketplace (addons directory).

    Returns addon types, descriptions, and available plans.
    """
    addons_dir = PROJECT_ROOT / "addons"

    if not addons_dir.exists():
        return {"addons": []}

    marketplace_addons = []

    # Scan addons directory
    for addon_dir in addons_dir.iterdir():
        if not addon_dir.is_dir() or addon_dir.name.startswith("."):
            continue

        addon_yml = addon_dir / "addon.yml"
        if not addon_yml.exists():
            continue

        try:
            with open(addon_yml, "r") as f:
                addon_meta = yaml.safe_load(f)

            # Read env.yml for plan details
            env_yml = addon_dir / "env.yml"
            plans = []
            if env_yml.exists():
                with open(env_yml, "r") as f:
                    env_data = yaml.safe_load(f)
                    plans_data = env_data.get("plans", {})
                    for plan_name, plan_config in plans_data.items():
                        plans.append(
                            {
                                "name": plan_name,
                                "resources": plan_config.get("resources", {}),
                            }
                        )

            marketplace_addons.append(
                {
                    "type": addon_dir.name,
                    "name": addon_meta.get("name", addon_dir.name.capitalize()),
                    "description": addon_meta.get("description", ""),
                    "category": addon_meta.get("category", "other"),
                    "version": addon_meta.get("version", "latest"),
                    "plans": plans,
                }
            )

        except Exception as e:
            print(f"Error reading addon {addon_dir.name}: {str(e)}")
            continue

    # Sort by category
    marketplace_addons.sort(key=lambda x: (x["category"], x["name"]))

    return {"addons": marketplace_addons}


@router.post("/{project_name}/provision")
async def provision_addon(project_name: str, request: AddonProvisionRequest):
    """
    Provision a new addon instance.

    Adds to config.yml, generates credentials in secrets.yml.
    """
    from dashboard.backend.services.config_service import ConfigService

    config_service = ConfigService(PROJECT_ROOT)

    try:
        # Read config
        config = config_service.read_config(project_name)
        secrets = config_service.read_secrets(project_name)

        # Determine category based on addon type
        category_map = {
            "postgres": "databases",
            "mongodb": "databases",
            "redis": "caches",
            "rabbitmq": "queues",
            "elasticsearch": "search",
            "caddy": "proxy",
        }

        category = category_map.get(request.addon_type, "other")

        # Ensure structure exists
        if "addons" not in config:
            config["addons"] = {}
        if category not in config["addons"]:
            config["addons"][category] = {}
        if "addons" not in secrets:
            secrets["addons"] = {}
        if request.addon_type not in secrets["addons"]:
            secrets["addons"][request.addon_type] = {}

        # Check if addon already exists
        if request.name in config["addons"].get(category, {}):
            raise HTTPException(
                status_code=400, detail=f"Addon {request.name} already exists"
            )

        # Add addon to config
        config["addons"][category][request.name] = {
            "type": request.addon_type,
            "plan": request.plan,
        }

        # Generate credentials
        addon_credentials = {
            "HOST": f"{request.name}",  # Will be internal docker service name
        }

        if request.addon_type == "postgres":
            addon_credentials.update(
                {
                    "PORT": 5432,
                    "USER": "postgres",
                    "PASSWORD": config_service.generate_secure_password(),
                    "DATABASE": request.name,
                }
            )
        elif request.addon_type == "redis":
            addon_credentials.update(
                {"PORT": 6379, "PASSWORD": config_service.generate_secure_password()}
            )
        elif request.addon_type == "rabbitmq":
            addon_credentials.update(
                {
                    "PORT": 5672,
                    "USER": "admin",
                    "PASSWORD": config_service.generate_secure_password(),
                    "VHOST": "/",
                }
            )
        elif request.addon_type == "mongodb":
            addon_credentials.update(
                {
                    "PORT": 27017,
                    "USER": "admin",
                    "PASSWORD": config_service.generate_secure_password(),
                    "DATABASE": request.name,
                }
            )

        secrets["addons"][request.addon_type][request.name] = addon_credentials

        # Save config and secrets
        config_service.write_config(project_name, config)
        config_service.write_secrets(project_name, secrets)

        return {
            "success": True,
            "message": f"Addon {request.name} provisioned successfully",
            "addon": {
                "name": request.name,
                "type": request.addon_type,
                "plan": request.plan,
                "reference": f"{category}.{request.name}",
            },
            "note": "Run 'superdeploy {project_name}:up' to deploy the addon",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/addons/{addon_ref}/attach")
async def attach_addon(project_name: str, addon_ref: str, request: AddonAttachRequest):
    """
    Attach an addon to an app.

    Updates app.addons in config.yml and restarts app containers.
    """
    from dashboard.backend.services.config_service import ConfigService
    from dashboard.backend.services.ssh_service import SSHConnectionPool

    config_service = ConfigService(PROJECT_ROOT)
    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Read config
        config = config_service.read_config(project_name)
        apps_config = config.get("apps", {})

        if request.app_name not in apps_config:
            raise HTTPException(
                status_code=404, detail=f"App {request.app_name} not found"
            )

        app_config = apps_config[request.app_name]

        # Ensure addons array exists
        if "addons" not in app_config:
            app_config["addons"] = []

        # Check if already attached
        for addon in app_config["addons"]:
            addon_check = addon if isinstance(addon, str) else addon.get("addon")
            if addon_check == addon_ref:
                raise HTTPException(
                    status_code=400,
                    detail=f"Addon {addon_ref} already attached to {request.app_name}",
                )

        # Add attachment
        if request.as_prefix:
            app_config["addons"].append({"addon": addon_ref, "as": request.as_prefix})
        else:
            app_config["addons"].append(addon_ref)

        # Save config
        config_service.write_config(project_name, config)

        # Restart app containers to pick up new env vars
        vm_name = app_config.get("vm")
        if vm_name:
            vms = ssh_pool.get_vm_info_from_state(project_name)
            if vm_name in vms:
                vm_ip = vms[vm_name].get("external_ip")
                ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

                compose_dir = f"/opt/superdeploy/projects/{project_name}/compose"
                restart_command = (
                    f"cd {compose_dir} && docker compose restart {request.app_name}-*"
                )

                try:
                    await ssh_pool.execute_command(
                        vm_ip, ssh_key_path, restart_command, timeout=60
                    )
                except Exception as e:
                    print(f"Warning: Failed to restart containers: {str(e)}")

        return {
            "success": True,
            "message": f"Addon {addon_ref} attached to {request.app_name}",
            "app_name": request.app_name,
            "addon_ref": addon_ref,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_name}/addons/{addon_ref}")
async def destroy_addon(project_name: str, addon_ref: str):
    """
    Destroy an addon.

    WARNING: This will delete all data in the addon.
    Removes from config.yml and secrets.yml.
    """
    from dashboard.backend.services.config_service import ConfigService
    from dashboard.backend.services.ssh_service import SSHConnectionPool

    config_service = ConfigService(PROJECT_ROOT)
    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Parse addon reference (category.name)
        if "." not in addon_ref:
            raise HTTPException(
                status_code=400, detail="Invalid addon reference format"
            )

        category, addon_name = addon_ref.split(".", 1)

        # Read config
        config = config_service.read_config(project_name)
        secrets = config_service.read_secrets(project_name)

        # Check if addon exists
        if (
            category not in config.get("addons", {})
            or addon_name not in config["addons"][category]
        ):
            raise HTTPException(status_code=404, detail=f"Addon {addon_ref} not found")

        addon_config = config["addons"][category][addon_name]
        addon_type = addon_config.get("type")

        # Check if addon is attached to any apps
        apps_config = config.get("apps", {})
        attached_apps = []
        for app_name, app_config in apps_config.items():
            app_addons = app_config.get("addons", [])
            for addon in app_addons:
                addon_check = addon if isinstance(addon, str) else addon.get("addon")
                if addon_check == addon_ref:
                    attached_apps.append(app_name)

        if attached_apps:
            raise HTTPException(
                status_code=400,
                detail=f"Addon is still attached to apps: {', '.join(attached_apps)}. Detach first.",
            )

        # Remove from config
        del config["addons"][category][addon_name]

        # Clean up empty category
        if not config["addons"][category]:
            del config["addons"][category]

        # Remove from secrets
        if addon_type and addon_type in secrets.get("addons", {}):
            if addon_name in secrets["addons"][addon_type]:
                del secrets["addons"][addon_type][addon_name]

        # Save config and secrets
        config_service.write_config(project_name, config)
        config_service.write_secrets(project_name, secrets)

        # Stop and remove addon containers via SSH
        # TODO: Implement container removal via docker compose down

        return {
            "success": True,
            "message": f"Addon {addon_ref} destroyed successfully",
            "addon_ref": addon_ref,
            "note": "Run 'superdeploy {project_name}:down' to remove the containers",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
