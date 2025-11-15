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
    containers,
    apps,
    addons,
    logs,
    metrics,
    settings,
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
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(apps.router, prefix="/api/apps", tags=["apps"])
app.include_router(addons.router, prefix="/api/addons", tags=["addons"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(resources.router, prefix="/api/resources", tags=["resources"])
app.include_router(config.router, prefix="/api/config", tags=["config"])


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "superdeploy-dashboard"}


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from database import init_db, SessionLocal
    from models import Project, Environment, VM
    from pathlib import Path
    import yaml

    try:
        init_db()
        print("✓ Database initialized")

        # Sync projects from filesystem
        superdeploy_root = Path(__file__).parent.parent.parent
        projects_dir = superdeploy_root / "projects"
        orchestrator_dir = superdeploy_root / "shared" / "orchestrator"
        print(f"📂 Looking for projects in: {projects_dir}")

        if not projects_dir.exists():
            print(f"⚠️  Projects directory does not exist: {projects_dir}")
            return

        db = SessionLocal()
        try:
            found_projects = []
            synced_count = 0

            # Sync orchestrator first (special case)
            if orchestrator_dir.exists():
                config_file = orchestrator_dir / "config.yml"
                state_file = orchestrator_dir / "state.yml"

                if config_file.exists() and state_file.exists():
                    found_projects.append("orchestrator")

                    existing = (
                        db.query(Project).filter(Project.name == "orchestrator").first()
                    )

                    if not existing:
                        with open(config_file, "r") as f:
                            config = yaml.safe_load(f)

                        new_project = Project(
                            name="orchestrator",
                            domain=None,
                            cloud_provider="gcp",
                            cloud_region=config.get("gcp", {}).get(
                                "region", "us-central1"
                            ),
                            cloud_zone=config.get("gcp", {}).get(
                                "zone", "us-central1-a"
                            ),
                        )
                        db.add(new_project)
                        db.flush()

                        for env_name in ["production", "staging", "review"]:
                            env = Environment(name=env_name, project_id=new_project.id)
                            db.add(env)

                        db.commit()
                        synced_count += 1
                        print("✓ Synced project: orchestrator")
                        project = new_project
                    else:
                        print("✓ Project exists: orchestrator")
                        project = existing

                    # Sync orchestrator VM
                    try:
                        with open(state_file, "r") as f:
                            state = yaml.safe_load(f)

                        vm_state = state.get("vm", {})
                        if vm_state:
                            existing_vm = (
                                db.query(VM)
                                .filter(
                                    VM.project_id == project.id,
                                    VM.name == "orchestrator",
                                )
                                .first()
                            )

                            if not existing_vm:
                                new_vm = VM(
                                    project_id=project.id,
                                    name="orchestrator",
                                    external_ip=vm_state.get("external_ip"),
                                    internal_ip=None,
                                    machine_type=vm_state.get("machine_type"),
                                    status=vm_state.get("status", "running"),
                                )
                                db.add(new_vm)
                                print(
                                    f"  ✓ Synced VM: orchestrator ({vm_state.get('external_ip')})"
                                )
                            else:
                                external_ip = vm_state.get("external_ip")
                                if (
                                    external_ip
                                    and existing_vm.external_ip != external_ip
                                ):
                                    existing_vm.external_ip = external_ip
                                    existing_vm.status = vm_state.get(
                                        "status", "running"
                                    )
                                    print(
                                        f"  🔄 VM updated: orchestrator ({external_ip})"
                                    )

                            db.commit()
                    except Exception as e:
                        print(f"⚠️  Failed to sync orchestrator VM: {e}")

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
                    # Set domain based on project name
                    domain = None
                    if project_dir.name == "cheapa":
                        domain = "cheapa.io"

                    new_project = Project(name=project_dir.name, domain=domain)
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

                # Sync VMs from state.yml for this project
                state_file = project_dir / "state.yml"
                if state_file.exists():
                    try:
                        with open(state_file, "r") as f:
                            state = yaml.safe_load(f)

                        vms_state = state.get("vms", {})
                        project = (
                            db.query(Project)
                            .filter(Project.name == project_dir.name)
                            .first()
                        )

                        for vm_role, vm_config in vms_state.items():
                            # VM name format: {project}-{role}-0
                            vm_name = f"{project_dir.name}-{vm_role}-0"

                            existing_vm = (
                                db.query(VM)
                                .filter(VM.project_id == project.id, VM.name == vm_name)
                                .first()
                            )

                            if not existing_vm:
                                new_vm = VM(
                                    project_id=project.id,
                                    name=vm_name,
                                    role=vm_role,
                                    external_ip=vm_config.get("external_ip"),
                                    internal_ip=vm_config.get("internal_ip"),
                                    machine_type=vm_config.get("machine_type"),
                                    status=vm_config.get("status", "running"),
                                )
                                db.add(new_vm)
                                print(
                                    f"  ✓ Synced VM: {vm_name} ({vm_config.get('external_ip')})"
                                )
                            else:
                                # Update IP if changed
                                external_ip = vm_config.get("external_ip")
                                if (
                                    external_ip
                                    and existing_vm.external_ip != external_ip
                                ):
                                    existing_vm.external_ip = external_ip
                                    existing_vm.internal_ip = vm_config.get(
                                        "internal_ip"
                                    )
                                    existing_vm.status = vm_config.get(
                                        "status", "running"
                                    )
                                    print(f"  🔄 VM updated: {vm_name} ({external_ip})")

                        db.commit()
                    except Exception as e:
                        print(f"⚠️  Failed to sync VMs for {project_dir.name}: {e}")

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
