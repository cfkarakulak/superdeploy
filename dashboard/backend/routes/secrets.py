"""Secret CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from dashboard.backend.database import get_db
from dashboard.backend.models import Secret

router = APIRouter(tags=["secrets"])


class SecretCreate(BaseModel):
    environment_id: int
    app: str
    key: str
    value: str


class SecretUpdate(BaseModel):
    value: str


class SecretResponse(BaseModel):
    id: int
    environment_id: int
    app: str
    key: str
    value: str

    class Config:
        from_attributes = True


@router.get("/environment/{environment_id}", response_model=List[SecretResponse])
def list_secrets(environment_id: int, db: Session = Depends(get_db)):
    """List all secrets for an environment."""
    secrets = db.query(Secret).filter(Secret.environment_id == environment_id).all()
    return secrets


@router.get("/{secret_id}", response_model=SecretResponse)
def get_secret(secret_id: int, db: Session = Depends(get_db)):
    """Get secret by ID."""
    secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    return secret


@router.post("/", response_model=SecretResponse)
def create_secret(secret: SecretCreate, db: Session = Depends(get_db)):
    """Create a new secret."""
    # Check if secret already exists
    existing = (
        db.query(Secret)
        .filter(
            Secret.environment_id == secret.environment_id,
            Secret.app == secret.app,
            Secret.key == secret.key,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400, detail="Secret with this key already exists"
        )

    db_secret = Secret(**secret.dict())
    db.add(db_secret)
    db.commit()
    db.refresh(db_secret)
    return db_secret


@router.put("/{secret_id}", response_model=SecretResponse)
def update_secret(
    secret_id: int, secret_update: SecretUpdate, db: Session = Depends(get_db)
):
    """Update a secret value."""
    db_secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not db_secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    db_secret.value = secret_update.value
    db.commit()
    db.refresh(db_secret)
    return db_secret


@router.delete("/{secret_id}")
def delete_secret(secret_id: int, db: Session = Depends(get_db)):
    """Delete a secret."""
    db_secret = db.query(Secret).filter(Secret.id == secret_id).first()
    if not db_secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    db.delete(db_secret)
    db.commit()
    return {"ok": True}


@router.post("/sync/{project_name}")
def sync_secrets_from_file(project_name: str, db: Session = Depends(get_db)):
    """Sync secrets from secrets.yml file to database."""
    import yaml
    from pathlib import Path
    from dashboard.backend.models import Project, Environment

    # Get project
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load secrets.yml
    secrets_path = (
        Path(__file__).parent.parent.parent.parent
        / "projects"
        / project_name
        / "secrets.yml"
    )

    if not secrets_path.exists():
        raise HTTPException(status_code=404, detail="secrets.yml not found")

    with open(secrets_path, "r") as f:
        secrets_data = yaml.safe_load(f)

    if not secrets_data or "secrets" not in secrets_data:
        return {"synced": 0, "message": "No secrets found in file"}

    synced_count = 0
    production_env = (
        db.query(Environment)
        .filter(Environment.project_id == project.id, Environment.name == "production")
        .first()
    )

    if not production_env:
        raise HTTPException(status_code=404, detail="Production environment not found")

    project_secrets = secrets_data["secrets"]

    # Sync shared secrets
    if "shared" in project_secrets:
        for key, value in project_secrets["shared"].items():
            existing = (
                db.query(Secret)
                .filter(
                    Secret.environment_id == production_env.id,
                    Secret.app == "shared",
                    Secret.key == key,
                )
                .first()
            )

            if not existing:
                new_secret = Secret(
                    environment_id=production_env.id,
                    app="shared",
                    key=key,
                    value=str(value),
                )
                db.add(new_secret)
                synced_count += 1
            else:
                if existing.value != str(value):
                    existing.value = str(value)
                    synced_count += 1

    # Sync app-specific secrets
    if "apps" in project_secrets:
        for app_name, app_secrets in project_secrets["apps"].items():
            for key, value in app_secrets.items():
                existing = (
                    db.query(Secret)
                    .filter(
                        Secret.environment_id == production_env.id,
                        Secret.app == app_name,
                        Secret.key == key,
                    )
                    .first()
                )

                if not existing:
                    new_secret = Secret(
                        environment_id=production_env.id,
                        app=app_name,
                        key=key,
                        value=str(value),
                    )
                    db.add(new_secret)
                    synced_count += 1
                else:
                    if existing.value != str(value):
                        existing.value = str(value)
                        synced_count += 1

    db.commit()
    return {"synced": synced_count, "message": f"Synced {synced_count} secrets"}


# Config Vars Management (File-based, Heroku-like)


@router.get("/config-vars/{project_name}/{app_name}")
async def get_config_vars(project_name: str, app_name: str, db: Session = Depends(get_db)):
    """
    Get config vars for an app (Heroku-like).

    Returns app-specific and shared secrets from DATABASE.
    """
    from dashboard.backend.models import Project, Environment, Addon

    try:
        # Get project and production environment
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        production_env = (
            db.query(Environment)
            .filter(Environment.project_id == project.id, Environment.name == "production")
            .first()
        )

        if not production_env:
            raise HTTPException(status_code=404, detail="Production environment not found")

        # Get secrets from DB
        app_secrets = (
            db.query(Secret)
            .filter(Secret.environment_id == production_env.id, Secret.app == app_name)
            .all()
        )

        shared_secrets = (
            db.query(Secret)
            .filter(Secret.environment_id == production_env.id, Secret.app == "shared")
            .all()
        )

        # Build response
        config_vars = []

        # Add app-specific secrets
        for secret in app_secrets:
            config_vars.append(
                {
                    "key": secret.key,
                    "value": secret.value,
                    "source": "app",
                    "editable": True,
                    "id": secret.id,
                }
            )

        # Add shared secrets
        for secret in shared_secrets:
            config_vars.append(
                {
                    "key": secret.key,
                    "value": secret.value,
                    "source": "shared",
                    "editable": True,
                    "id": secret.id,
                }
            )

        # Get addon-generated vars (from addon credentials)
        addons = (
            db.query(Addon)
            .filter(Addon.project_id == project.id)
            .all()
        )

        for addon in addons:
            # Check if this addon is attached to this app
            if addon.attachments:
                for attachment in addon.attachments:
                    if attachment.get("app_name") == app_name:
                        # Add addon credentials as read-only vars
                        if addon.credentials:
                            prefix = attachment.get("as_prefix", addon.type.upper())
                            for key, value in addon.credentials.items():
                                env_key = f"{prefix}_{key.upper()}"
                                config_vars.append(
                                    {
                                        "key": env_key,
                                        "value": str(value),
                                        "source": "addon",
                                        "editable": False,
                                    }
                                )

        return {"app_name": app_name, "config_vars": config_vars}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfigVarUpdate(BaseModel):
    key: str
    value: str


@router.post("/config-vars/{project_name}/{app_name}")
async def set_config_var(
    project_name: str,
    app_name: str,
    config_var: ConfigVarUpdate,
    db: Session = Depends(get_db)
):
    """
    Set or update a config var for an app.

    Updates DATABASE only. No file writes, no SSH calls.
    """
    from dashboard.backend.models import Project, Environment

    try:
        # Get project and production environment
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        production_env = (
            db.query(Environment)
            .filter(Environment.project_id == project.id, Environment.name == "production")
            .first()
        )

        if not production_env:
            raise HTTPException(status_code=404, detail="Production environment not found")

        # Check if secret exists
        existing = (
            db.query(Secret)
            .filter(
                Secret.environment_id == production_env.id,
                Secret.app == app_name,
                Secret.key == config_var.key,
            )
            .first()
        )

        if existing:
            # Update existing secret
            existing.value = config_var.value
        else:
            # Create new secret
            new_secret = Secret(
                environment_id=production_env.id,
                app=app_name,
                key=config_var.key,
                value=config_var.value,
            )
            db.add(new_secret)

        db.commit()

        return {
            "success": True,
            "message": f"Config var {config_var.key} updated for {app_name}",
            "key": config_var.key,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config-vars/{project_name}/{app_name}/{key}")
async def delete_config_var(project_name: str, app_name: str, key: str):
    """
    Delete a config var for an app.

    Removes from secrets.yml, syncs, and restarts containers.
    """
    from pathlib import Path
    from dashboard.backend.services.config_service import ConfigService
    from dashboard.backend.services.ssh_service import SSHConnectionPool

    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    config_service = ConfigService(PROJECT_ROOT)
    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Delete from secrets.yml
        config_service.delete_app_secret(project_name, app_name, key)

        # Restart containers (same as set)
        config = config_service.read_config(project_name)
        apps_config = config.get("apps", {})

        if app_name in apps_config:
            app_config = apps_config[app_name]
            vm_name = app_config.get("vm")

            vms = ssh_pool.get_vm_info_from_state(project_name)

            if vm_name in vms:
                vm_ip = vms[vm_name].get("external_ip")
                ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

                compose_dir = f"/opt/superdeploy/projects/{project_name}/compose"
                restart_command = (
                    f"cd {compose_dir} && docker compose restart {app_name}-*"
                )

                try:
                    await ssh_pool.execute_command(
                        vm_ip, ssh_key_path, restart_command, timeout=60
                    )
                except Exception as e:
                    print(f"Warning: Failed to restart containers: {str(e)}")

        return {
            "success": True,
            "message": f"Config var {key} deleted from {app_name}",
            "key": key,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()
