"""
Logs routes for streaming application logs.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
from utils.cli import get_cli

router = APIRouter()


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class LogsRequest(BaseModel):
    """Request model for logs streaming."""

    lines: int = 100


async def stream_logs(project_name: str, app_name: str, lines: int = 100):
    """
    Stream logs from superdeploy CLI command.

    Yields log lines as they come from the CLI.
    Keeps ANSI color codes for frontend rendering.
    """
    try:
        cli = get_cli()

        # Stream logs using the centralized CLI executor
        async for line in cli.execute(
            f"{project_name}:logs", args=["-a", app_name, "-n", str(lines)]
        ):
            # Keep ANSI codes for colored terminal output in frontend
            yield f"data: {line}\n\n"

    except Exception as e:
        yield f"data: [ERROR] Failed to stream logs: {str(e)}\n\n"


@router.get("/{project_name}/apps/{app_name}/logs/stream")
async def stream_app_logs(project_name: str, app_name: str, lines: int = 100):
    """
    Stream application logs in real-time using Server-Sent Events (SSE).

    Args:
        project_name: Name of the project
        app_name: Name of the application
        lines: Number of recent lines to show before streaming

    Returns:
        StreamingResponse with real-time logs
    """
    return StreamingResponse(
        stream_logs(project_name, app_name, lines),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
