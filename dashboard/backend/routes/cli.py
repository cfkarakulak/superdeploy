"""CLI command execution routes."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Optional

router = APIRouter(tags=["cli"])

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class InitProjectRequest(BaseModel):
    """Request to initialize a new project."""

    project_name: str
    gcp_project: str
    gcp_region: str = "us-central1"
    github_org: str
    apps: Dict[str, Dict] = {}
    addons: Dict[str, Dict] = {}


class CommandRequest(BaseModel):
    """Generic command request."""

    project_name: str
    command: Optional[str] = None


@router.post("/init")
async def init_project(request: InitProjectRequest):
    """Initialize a new project."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)

    async def generate():
        async for line in executor.init_project(
            project_name=request.project_name,
            gcp_project=request.gcp_project,
            gcp_region=request.gcp_region,
            github_org=request.github_org,
            apps=request.apps,
            addons=request.addons,
        ):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/generate")
async def generate_deployment_files(request: CommandRequest):
    """Generate deployment files for a project."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)

    async def generate():
        async for line in executor.generate_deployment_files(request.project_name):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/deploy")
async def deploy_project(request: CommandRequest):
    """Deploy a project."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)

    async def generate():
        async for line in executor.deploy_project(request.project_name):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/destroy")
async def destroy_project(request: CommandRequest):
    """Destroy a project."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)

    async def generate():
        async for line in executor.destroy_project(request.project_name):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/status")
async def get_project_status(request: CommandRequest):
    """Get project status."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)

    async def generate():
        async for line in executor.get_project_status(request.project_name):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/available-projects")
async def get_available_projects():
    """Get list of available projects."""
    from dashboard.backend.services.cli_executor import CLIExecutor

    executor = CLIExecutor(PROJECT_ROOT)
    projects = executor.get_available_projects()

    return {"projects": projects}
