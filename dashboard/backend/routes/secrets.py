"""Secret management routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.cli import get_cli

router = APIRouter(tags=["secrets"])


# Secrets Management (CLI-based, Real-time)


class SecretUpdateRequest(BaseModel):
    key: str
    value: str


@router.get("/secrets/{project_name}/{app_name}")
async def get_app_secrets(
    project_name: str,
    app_name: str,
):
    """
    Get secrets for an app (Heroku-like).

    Returns app-specific and shared secrets from secrets.yml via CLI.
    Also returns addon secrets with proper prefixes.
    """
    try:
        cli = get_cli()

        # Use CLI to get all secrets (app + shared + addon)
        config_data = await cli.execute_json(
            f"{project_name}:config:list", args=["--app", app_name]
        )

        secrets = []

        # Add all environment variables from CLI
        # CLI already merges shared + app-specific + addon secrets
        for key, value in config_data.get("variables", {}).items():
            # Detect source based on key patterns
            if any(
                addon_prefix in key
                for addon_prefix in [
                    "DATABASE_",
                    "RABBITMQ_",
                    "REDIS_",
                    "MONGODB_",
                    "ELASTICSEARCH_",
                ]
            ):
                source = "addon"
                editable = False
            else:
                source = "app"
                editable = True

            secrets.append(
                {
                    "key": key,
                    "value": str(value),
                    "source": source,
                    "editable": editable,
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
):
    """
    Set or update a secret for an app.

    Updates secrets.yml file via CLI.
    """
    try:
        cli = get_cli()

        # Use CLI to set the secret
        result = await cli.execute_json(
            f"{project_name}:config:set",
            args=["-a", app_name, secret_data.key, secret_data.value],
        )

        if result.get("success"):
            return {
                "success": True,
                "message": f"Secret {secret_data.key} updated for {app_name}",
                "key": secret_data.key,
            }
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to set secret")
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/secrets/{project_name}/{app_name}/{key}")
async def delete_app_secret(
    project_name: str,
    app_name: str,
    key: str,
):
    """
    Delete a secret for an app.

    Removes from secrets.yml file via CLI.
    """
    try:
        cli = get_cli()

        # Use CLI to unset the secret
        result = await cli.execute_json(
            f"{project_name}:config:unset", args=["-a", app_name, key]
        )

        if result.get("success"):
            return {
                "success": True,
                "message": f"Secret {key} deleted from {app_name}",
                "key": key,
            }
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to delete secret")
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
