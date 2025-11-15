"""
Unified CLI JSON executor for all dashboard CLI requests.
Single endpoint that handles all superdeploy CLI commands with JSON output.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from utils.cli import get_cli

router = APIRouter(tags=["cli-json"])


class CLIRequest(BaseModel):
    """Request to execute a CLI command."""

    command: str  # e.g., "cheapa:ps", "cheapa:addons:list"
    args: Optional[List[str]] = None  # Additional arguments


class CLIResponse(BaseModel):
    """Response from CLI command execution."""

    success: bool
    data: dict
    error: Optional[str] = None


@router.post("/execute")
async def execute_cli_command(request: CLIRequest) -> CLIResponse:
    """
    Execute any superdeploy CLI command with JSON output.

    This is the single unified endpoint for all CLI operations in the dashboard.
    All CLI commands are executed through this endpoint with --json flag.

    Args:
        request: CLI command and optional arguments

    Returns:
        CLIResponse with parsed JSON data or error

    Examples:
        POST /api/cli-json/execute
        {"command": "cheapa:ps"}

        POST /api/cli-json/execute
        {"command": "cheapa:releases:list", "args": ["-a", "api"]}

        POST /api/cli-json/execute
        {"command": "cheapa:config", "args": ["-a", "api"]}
    """
    try:
        cli = get_cli()
        data = await cli.execute_json(request.command, args=request.args)

        return CLIResponse(success=True, data=data)

    except RuntimeError as e:
        return CLIResponse(success=False, data={}, error=str(e))
    except Exception as e:
        return CLIResponse(success=False, data={}, error=f"Unexpected error: {str(e)}")


@router.get("/{project_name}/{command:path}")
async def execute_cli_command_get(
    project_name: str, command: str, app: Optional[str] = None
) -> CLIResponse:
    """
    Execute CLI command via GET request (simplified).

    Args:
        project_name: Project name
        command: Command to execute (e.g., "ps", "addons/list", "config")
        app: Optional app name for filtering

    Returns:
        CLIResponse with parsed JSON data

    Examples:
        GET /api/cli-json/cheapa/ps
        GET /api/cli-json/cheapa/addons/list
        GET /api/cli-json/cheapa/config?app=api
    """
    try:
        cli = get_cli()

        # Build full command
        full_command = f"{project_name}:{command.replace('/', ':')}"

        # Add app filter if provided
        args = []
        if app:
            args.extend(["-a", app])

        data = await cli.execute_json(full_command, args=args if args else None)

        return CLIResponse(success=True, data=data)

    except RuntimeError as e:
        return CLIResponse(success=False, data={}, error=str(e))
    except Exception as e:
        return CLIResponse(success=False, data={}, error=f"Unexpected error: {str(e)}")
