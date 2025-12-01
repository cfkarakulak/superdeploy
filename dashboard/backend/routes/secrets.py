"""Secret management routes - Database-backed with FK relationships."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from models import Secret, SecretAlias, Project, App

# Get superdeploy root directory
SUPERDEPLOY_ROOT = Path(__file__).parent.parent.parent.resolve()

router = APIRouter(tags=["secrets"])


# Request/Response Models
class SecretUpdateRequest(BaseModel):
    key: str
    value: str


class AliasUpdateRequest(BaseModel):
    alias_key: str
    target_key: str


def get_project_id(db: Session, project_name: str) -> int:
    """Get project ID from name, raise 404 if not found."""
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_name}' not found"
        )
    return project.id


def get_app_id(db: Session, project_id: int, app_name: str) -> int:
    """Get app ID from name and project, raise 404 if not found."""
    app = (
        db.query(App).filter(App.project_id == project_id, App.name == app_name).first()
    )
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_name}' not found")
    return app.id


@router.get("/secrets/{project_name}/{app_name}")
async def get_app_secrets(
    project_name: str,
    app_name: str,
    environment: str = "production",
    db: Session = Depends(get_db),
):
    """
    Get secrets for an app from database.

    Returns merged secrets: shared + addon + app-specific + resolved aliases.
    """
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        secrets_list = []

        # 1. Get shared secrets (app_id=NULL)
        shared_secrets = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.app_id.is_(None),
                Secret.environment == environment,
            )
            .all()
        )

        for secret in shared_secrets:
            secrets_list.append(
                {
                    "key": secret.key,
                    "value": secret.value,
                    "source": secret.source,
                    "editable": secret.editable,
                }
            )

        # 2. Get app-specific secrets
        app_secrets = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.app_id == app_id,
                Secret.environment == environment,
            )
            .all()
        )

        for secret in app_secrets:
            secrets_list.append(
                {
                    "key": secret.key,
                    "value": secret.value,
                    "source": secret.source,
                    "editable": secret.editable,
                }
            )

        # 3. Get aliases and resolve them
        aliases = (
            db.query(SecretAlias)
            .filter(
                SecretAlias.project_id == project_id,
                SecretAlias.app_id == app_id,
            )
            .all()
        )

        for alias in aliases:
            # Resolve alias to actual value
            target_secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.key == alias.target_key,
                    Secret.environment == environment,
                )
                .first()
            )

            if target_secret:
                secrets_list.append(
                    {
                        "key": alias.alias_key,
                        "value": target_secret.value,
                        "source": "alias",
                        "editable": True,  # Aliases are editable (can remove alias)
                        "target_key": alias.target_key,  # Include target for frontend
                    }
                )

        return {"app_name": app_name, "secrets": secrets_list}

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
    Set or update a secret for an app in database.
    """
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        # Upsert (update or insert)
        secret = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.app_id == app_id,
                Secret.key == secret_data.key,
                Secret.environment == environment,
            )
            .first()
        )

        if secret:
            secret.value = secret_data.value
        else:
            secret = Secret(
                project_id=project_id,
                app_id=app_id,
                key=secret_data.key,
                value=secret_data.value,
                environment=environment,
                source="app",
                editable=True,
            )
            db.add(secret)

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
    Delete a secret for an app from database.
    """
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        secret = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.app_id == app_id,
                Secret.key == key,
                Secret.environment == environment,
            )
            .first()
        )

        if not secret:
            raise HTTPException(status_code=404, detail="Secret not found")

        if not secret.editable:
            raise HTTPException(
                status_code=403, detail="This secret cannot be deleted (addon secret)"
            )

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


# ============================================================================
# Aliases Management
# ============================================================================


@router.get("/aliases/{project_name}/{app_name}")
async def get_app_aliases(
    project_name: str,
    app_name: str,
    db: Session = Depends(get_db),
):
    """Get all aliases for an app."""
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        aliases = (
            db.query(SecretAlias)
            .filter(
                SecretAlias.project_id == project_id,
                SecretAlias.app_id == app_id,
            )
            .all()
        )

        return {
            "aliases": [
                {
                    "alias_key": alias.alias_key,
                    "target_key": alias.target_key,
                    "created_at": alias.created_at.isoformat()
                    if alias.created_at
                    else None,
                }
                for alias in aliases
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aliases/{project_name}/{app_name}")
async def create_alias(
    project_name: str,
    app_name: str,
    alias_data: AliasUpdateRequest,
    db: Session = Depends(get_db),
):
    """Create or update an alias."""
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        # Upsert
        alias = (
            db.query(SecretAlias)
            .filter(
                SecretAlias.project_id == project_id,
                SecretAlias.app_id == app_id,
                SecretAlias.alias_key == alias_data.alias_key,
            )
            .first()
        )

        if alias:
            alias.target_key = alias_data.target_key
        else:
            alias = SecretAlias(
                project_id=project_id,
                app_id=app_id,
                alias_key=alias_data.alias_key,
                target_key=alias_data.target_key,
            )
            db.add(alias)

        db.commit()

        return {
            "success": True,
            "message": f"Alias {alias_data.alias_key} created/updated",
            "alias_key": alias_data.alias_key,
            "target_key": alias_data.target_key,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/aliases/{project_name}/{app_name}/{alias_key}")
async def delete_alias(
    project_name: str,
    app_name: str,
    alias_key: str,
    db: Session = Depends(get_db),
):
    """Delete an alias."""
    try:
        project_id = get_project_id(db, project_name)
        app_id = get_app_id(db, project_id, app_name)

        alias = (
            db.query(SecretAlias)
            .filter(
                SecretAlias.project_id == project_id,
                SecretAlias.app_id == app_id,
                SecretAlias.alias_key == alias_key,
            )
            .first()
        )

        if not alias:
            raise HTTPException(status_code=404, detail="Alias not found")

        db.delete(alias)
        db.commit()

        return {
            "success": True,
            "message": f"Alias {alias_key} deleted",
            "alias_key": alias_key,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GitHub Sync
# ============================================================================


@router.post("/sync/{project_name}/{app_name}")
async def sync_secrets(
    project_name: str,
    app_name: str,
    environment: str = "production",
):
    """
    Sync secrets to GitHub for specific app.

    Reads from database and syncs to GitHub.
    Streams CLI output in real-time.
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    async def stream_logs():
        try:
            # Execute vars:sync command (CLI now reads from database)
            process = await asyncio.create_subprocess_exec(
                "./superdeploy.sh",
                f"{project_name}:vars:sync",
                "--app",
                app_name,
                "--env",
                environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(SUPERDEPLOY_ROOT),
            )

            # Stream output
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    yield line

            await process.wait()

        except Exception as e:
            yield f"\nError: {str(e)}\n".encode()

    return StreamingResponse(stream_logs(), media_type="text/plain")


@router.post("/reload/{project_name}/{app_name}")
async def reload_containers(
    project_name: str,
    app_name: str,
):
    """
    Reload (restart) containers for a specific app to apply new environment variables.

    This will perform a zero-downtime restart of all processes for the app.
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    async def stream_logs():
        try:
            # Execute restart command using existing CLI
            process = await asyncio.create_subprocess_exec(
                "./superdeploy.sh",
                f"{project_name}:restart",
                "-a",
                app_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(SUPERDEPLOY_ROOT),
            )

            # Stream output
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    yield line

            await process.wait()

        except Exception as e:
            yield f"\nError: {str(e)}\n".encode()

    return StreamingResponse(stream_logs(), media_type="text/plain")
