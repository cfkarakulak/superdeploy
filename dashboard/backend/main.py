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
    containers,
    apps,
    addons,
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(secrets.router, prefix="/api/secrets", tags=["secrets"])
app.include_router(
    environments.router, prefix="/api/environments", tags=["environments"]
)
app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(cli.router, prefix="/api/cli", tags=["cli"])
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(apps.router, prefix="/api/apps", tags=["apps"])
app.include_router(addons.router, prefix="/api/addons", tags=["addons"])


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "superdeploy-dashboard"}


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from database import init_db, SessionLocal
    from models import Project, Environment
    from pathlib import Path

    try:
        init_db()
        print("✓ Database initialized")

        # Sync projects from filesystem
        projects_dir = Path(__file__).parent.parent.parent / "projects"
        print(f"📂 Looking for projects in: {projects_dir}")

        if not projects_dir.exists():
            print(f"⚠️  Projects directory does not exist: {projects_dir}")
            return

        db = SessionLocal()
        try:
            found_projects = []
            synced_count = 0

            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir() or project_dir.name.startswith("."):
                    continue

                # Only sync projects that have config.yml
                config_file = project_dir / "config.yml"
                if not config_file.exists():
                    print(f"⚠️  Skipping {project_dir.name} (no config.yml)")
                    continue

                found_projects.append(project_dir.name)

                # Check if project exists in DB
                existing = (
                    db.query(Project).filter(Project.name == project_dir.name).first()
                )

                if not existing:
                    # Create project
                    new_project = Project(name=project_dir.name)
                    db.add(new_project)
                    db.flush()

                    # Create default environments
                    for env_name in ["production", "staging", "review"]:
                        env = Environment(name=env_name, project_id=new_project.id)
                        db.add(env)

                    db.commit()
                    synced_count += 1
                    print(f"✓ Synced project: {project_dir.name}")
                else:
                    print(f"✓ Project exists: {project_dir.name}")

            if found_projects:
                print(
                    f"📊 Found {len(found_projects)} project(s): {', '.join(found_projects)}"
                )
                if synced_count > 0:
                    print(f"🔄 Synced {synced_count} new project(s) to database")
            else:
                print("⚠️  No valid projects found (projects need config.yml)")

        except Exception as e:
            print(f"❌ Error syncing projects: {e}")
            import traceback

            traceback.print_exc()
        finally:
            db.close()

    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback

        traceback.print_exc()


def start_server(port: int = 8401, host: str = "127.0.0.1"):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
