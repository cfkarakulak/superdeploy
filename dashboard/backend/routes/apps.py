from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Project, App

router = APIRouter(tags=["apps"])


@router.get("/{project_name}/list")
async def list_apps(project_name: str, db: Session = Depends(get_db)):
    """
    List all apps for a project from database.

    Database is the master source, not config.yml.
    """
    # Get project
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get apps from DB
    apps = db.query(App).filter(App.project_id == project.id).all()

    apps_list = []
    for app in apps:
        apps_list.append(
            {
                "name": app.name,
                "type": app.type,
                "domain": app.domain,
                "vm": app.vm,
                "port": app.port,
                "repo": app.repo,
                "owner": app.owner,
            }
        )

    return {"apps": apps_list}
