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
    allow_origins=["http://localhost:6000", "http://127.0.0.1:6000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from dashboard.backend.routes import projects, secrets, environments

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(secrets.router, prefix="/api/secrets", tags=["secrets"])
app.include_router(
    environments.router, prefix="/api/environments", tags=["environments"]
)


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "superdeploy-dashboard"}


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from dashboard.backend.database import init_db

    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"⚠ Database initialization warning: {e}")


def start_server(port: int = 6001, host: str = "127.0.0.1"):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
