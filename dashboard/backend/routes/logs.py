"""
Logs routes for streaming application logs.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
from pathlib import Path
import re

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
    """
    try:
        # Superdeploy CLI command
        cmd = ["superdeploy", f"{project_name}:logs", "-a", app_name, "-n", str(lines)]

        # Start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path(__file__).parent.parent.parent.parent,  # superdeploy root
        )

        # Stream output line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            # Decode and strip ANSI codes
            decoded_line = line.decode("utf-8", errors="replace")
            clean_line = strip_ansi_codes(decoded_line)

            # Yield the line with newline for SSE format
            yield f"data: {clean_line}\n\n"

        await process.wait()

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
