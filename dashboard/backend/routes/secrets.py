"""Secret management routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Secret

router = APIRouter(tags=["secrets"])


# Secrets Management (Database-based, Heroku-like)


class SecretUpdateRequest(BaseModel):
    key: str
    value: str


@router.get("/secrets/{project_name}/{app_name}")
async def get_app_secrets(
    project_name: str,
    app_name: str,
    environment: str = "production",
    db: Session = Depends(get_db),
):
    """
    Get secrets for an app (Heroku-like).

    Returns app-specific and shared secrets from DATABASE.
    """
    from models import Project, Environment, Addon

    try:
        # Get project and specified environment
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        env = (
            db.query(Environment)
            .filter(
                Environment.project_id == project.id, Environment.name == environment
            )
            .first()
        )

        if not env:
            raise HTTPException(
                status_code=404,
                detail=f"{environment.capitalize()} environment not found",
            )

        # Get secrets from DB
        app_secrets = (
            db.query(Secret)
            .filter(Secret.environment_id == env.id, Secret.app == app_name)
            .all()
        )

        shared_secrets = (
            db.query(Secret)
            .filter(Secret.environment_id == env.id, Secret.app == "shared")
            .all()
        )

        # Build response
        secrets = []

        # Add app-specific secrets
        for secret in app_secrets:
            secrets.append(
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
            secrets.append(
                {
                    "key": secret.key,
                    "value": secret.value,
                    "source": "shared",
                    "editable": True,
                    "id": secret.id,
                }
            )

        # Get addon-generated secrets (from addon credentials)
        addons = db.query(Addon).filter(Addon.project_id == project.id).all()

        for addon in addons:
            # Check if this addon is attached to this app
            if addon.attachments:
                for attachment in addon.attachments:
                    if attachment.get("app_name") == app_name:
                        # Add addon credentials as read-only secrets
                        if addon.credentials:
                            prefix = attachment.get("as_prefix", addon.type.upper())
                            for key, value in addon.credentials.items():
                                env_key = f"{prefix}_{key.upper()}"
                                secrets.append(
                                    {
                                        "key": env_key,
                                        "value": str(value),
                                        "source": "addon",
                                        "editable": False,
                                    }
                                )

        return {"app_name": app_name, "secrets": secrets}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/secrets/{project_name}/{app_name}")
async def set_app_secret(
    project_name: str,
    app_name: str,
    secret_data: SecretUpdateRequest,
    environment: str = "production",
    db: Session = Depends(get_db),
):
    """
    Set or update a secret for an app.

    Updates DATABASE only. No file writes, no SSH calls.
    """
    from models import Project, Environment

    try:
        # Get project and specified environment
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        env = (
            db.query(Environment)
            .filter(
                Environment.project_id == project.id, Environment.name == environment
            )
            .first()
        )

        if not env:
            raise HTTPException(
                status_code=404,
                detail=f"{environment.capitalize()} environment not found",
            )

        # Check if secret exists
        existing = (
            db.query(Secret)
            .filter(
                Secret.environment_id == env.id,
                Secret.app == app_name,
                Secret.key == secret_data.key,
            )
            .first()
        )

        if existing:
            # Update existing secret
            existing.value = secret_data.value
        else:
            # Create new secret
            new_secret = Secret(
                environment_id=env.id,
                app=app_name,
                key=secret_data.key,
                value=secret_data.value,
            )
            db.add(new_secret)

        db.commit()

        return {
            "success": True,
            "message": f"Secret {secret_data.key} updated for {app_name}",
            "key": secret_data.key,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/secrets/{project_name}/{app_name}/{key}")
async def delete_app_secret(
    project_name: str,
    app_name: str,
    key: str,
    environment: str = "production",
    db: Session = Depends(get_db),
):
    """
    Delete a secret for an app.

    Removes from DATABASE only. No file writes, no SSH calls.
    """
    from models import Project, Environment

    try:
        # Get project and specified environment
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        env = (
            db.query(Environment)
            .filter(
                Environment.project_id == project.id, Environment.name == environment
            )
            .first()
        )

        if not env:
            raise HTTPException(
                status_code=404,
                detail=f"{environment.capitalize()} environment not found",
            )

        # Find and delete secret
        secret = (
            db.query(Secret)
            .filter(
                Secret.environment_id == env.id,
                Secret.app == app_name,
                Secret.key == key,
            )
            .first()
        )

        if not secret:
            raise HTTPException(status_code=404, detail="Secret not found")

        db.delete(secret)
        db.commit()

        return {
            "success": True,
            "message": f"Secret {key} deleted from {app_name}",
            "key": key,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
