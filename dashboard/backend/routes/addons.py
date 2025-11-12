from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["addons"])


@router.get("/{project_name}/list")
async def list_addons(project_name: str):
    """
    List all provisioned addons for a project from database.

    Database is the master source, not config.yml.
    """
    from database import SessionLocal
    from models import Project, Addon

    db = SessionLocal()

    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get addons from DB
        addons = db.query(Addon).filter(Addon.project_id == project.id).all()

        addons_list = []
        for addon in addons:
            addons_list.append(
                {
                    "name": addon.name,
                    "type": addon.type,
                    "category": addon.category,
                    "plan": addon.plan,
                    "reference": f"{addon.category}.{addon.name}",
                    "attachments": addon.attachments or [],
                    "status": addon.status,
                }
            )

        return {"addons": addons_list}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
