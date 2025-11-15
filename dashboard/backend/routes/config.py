"""
Config and environment variable routes using CLI JSON output.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.cli import get_cli

router = APIRouter(tags=["config"])


class ConfigSetRequest(BaseModel):
    """Request to set a config variable."""

    key: str
    value: str
    app: str = None


class EnvSetRequest(BaseModel):
    """Request to set an environment variable."""

    key: str
    value: str
    app: str = None


@router.get("/{project_name}/config")
async def get_config(project_name: str, app: str = None):
    """
    Get configuration variables using unified CLI JSON endpoint.

    Args:
        project_name: Name of the project
        app: Optional app name to filter config for specific app

    Returns:
        Configuration variables (sensitive values masked)
    """
    try:
        from utils.cli import get_cli

        cli = get_cli()

        args = []
        if app:
            args.extend(["-a", app])

        data = await cli.execute_json(
            f"{project_name}:config", args=args if args else None
        )
        return data

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/config")
async def set_config(project_name: str, request: ConfigSetRequest):
    """
    Set a configuration variable.

    Args:
        project_name: Name of the project
        request: Config set request with key, value, and optional app

    Returns:
        Success message
    """
    try:
        cli = get_cli()

        args = [f"{request.key}={request.value}"]
        if request.app:
            args.extend(["-a", request.app])

        # Note: config:set doesn't support JSON output yet, so we use execute_simple
        output, exit_code = await cli.execute_simple(
            f"{project_name}:config:set", args=args
        )

        if exit_code != 0:
            raise RuntimeError(f"Config set failed: {output}")

        return {
            "status": "success",
            "message": f"Set {request.key} successfully",
            "output": output,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/env")
async def get_env_vars(project_name: str, app: str = None, show_all: bool = False):
    """
    Get environment variables using unified CLI JSON endpoint.

    Args:
        project_name: Name of the project (not used for env:list, but kept for consistency)
        app: Optional app name to filter env vars for specific app
        show_all: Show all env vars including system vars

    Returns:
        Environment variables (sensitive values masked)
    """
    try:
        from utils.cli import get_cli

        cli = get_cli()

        args = []
        if app:
            args.extend(["-a", app])
        if show_all:
            args.append("--all")

        # Note: env:list is a global command, not project-specific
        data = await cli.execute_json("env:list", args=args if args else None)
        return data

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/env")
async def set_env_var(project_name: str, request: EnvSetRequest):
    """
    Set an environment variable.

    Args:
        project_name: Name of the project
        request: Env set request with key, value, and optional app

    Returns:
        Success message
    """
    try:
        cli = get_cli()

        args = [f"{request.key}={request.value}"]
        if request.app:
            args.extend(["-a", request.app])

        # Note: env:set doesn't support JSON output yet, so we use execute_simple
        output, exit_code = await cli.execute_simple(
            f"{project_name}:env:set", args=args
        )

        if exit_code != 0:
            raise RuntimeError(f"Env set failed: {output}")

        return {
            "status": "success",
            "message": f"Set {request.key} successfully",
            "output": output,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
