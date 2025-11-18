"""FastAPI application for SuperDeploy Dashboard."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="SuperDeploy Dashboard",
    description="Local dashboard for managing secrets across environments",
    version="1.0.0",
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8400", "http://127.0.0.1:8400"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from routes import (
    projects,
    secrets,
    environments,
    github,
    cli,
    cli_json,
    apps,
    addons,
    logs,
    metrics,
    resources,
    config,
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(secrets.router, prefix="/api/secrets", tags=["secrets"])
app.include_router(
    environments.router, prefix="/api/environments", tags=["environments"]
)
app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(cli.router, prefix="/api/cli", tags=["cli"])
app.include_router(cli_json.router, prefix="/api/cli-json", tags=["cli-json"])
app.include_router(apps.router, prefix="/api/apps", tags=["apps"])
app.include_router(addons.router, prefix="/api/addons", tags=["addons"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(resources.router, prefix="/api/resources", tags=["resources"])
app.include_router(config.router, prefix="/api/config", tags=["config"])


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "superdeploy-dashboard"}


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from database import init_db

    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback

        traceback.print_exc()


def start_server(port: int = 8401, host: str = "127.0.0.1"):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
