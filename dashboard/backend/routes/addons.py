from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["addons"])


@router.get("/{project_name}/list")
async def list_addons(project_name: str):
    """
    List all provisioned addons for a project using unified CLI JSON endpoint.

    This uses the CLI's JSON output which reads from config.yml.
    """
    try:
        # Use unified CLI JSON executor
        from utils.cli import get_cli

        cli = get_cli()
        data = await cli.execute_json(f"{project_name}:addons:list")

        return data

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/list-db")
async def list_addons_from_db(project_name: str):
    """
    List all provisioned addons for a project from database.

    This is the legacy endpoint that reads from the database.
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
