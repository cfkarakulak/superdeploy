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


