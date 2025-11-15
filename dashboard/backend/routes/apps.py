from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Project, App
from pydantic import BaseModel

router = APIRouter(tags=["apps"])


class SwitchVersionRequest(BaseModel):
    """Request to switch to a different version."""

    git_sha: str


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


@router.get("/{project_name}/ps")
async def get_app_processes(project_name: str, db: Session = Depends(get_db)):
    """
    Get application processes using unified CLI JSON endpoint.

    Returns process information for all apps including replicas, ports, etc.
    """
    try:
        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Use unified CLI JSON executor
        from utils.cli import get_cli

        cli = get_cli()
        data = await cli.execute_json(f"{project_name}:ps")

        return data

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/{app_name}/releases")
async def get_releases(project_name: str, app_name: str, db: Session = Depends(get_db)):
    """
    Get deployment history (releases) for an app using CLI command.
    Enriches data with GitHub API (commit messages, authors, etc).

    Returns:
    - version: Release version
    - git_sha: Git commit SHA (full and short)
    - deployed_by: Who deployed it
    - deployed_at: When it was deployed
    - branch: Git branch
    - commit_message: Commit message from GitHub
    - author: GitHub commit author info
    """
    try:
        from utils.cli import get_cli
        import json
        import httpx
        from models import Setting

        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Use centralized CLI executor with JSON output
        cli = get_cli()

        # Execute releases:list command with --json flag
        output_lines = []
        async for line in cli.execute(
            f"{project_name}:releases:list", args=["-a", app_name, "--json"]
        ):
            output_lines.append(line)

        clean_output = "".join(output_lines).strip()

        # Parse JSON output
        releases_data = json.loads(clean_output)
        releases_list = releases_data.get("releases", [])

        print(f"DEBUG: Parsed {len(releases_list)} releases from CLI JSON output")

        # Shorten git SHAs (CLI returns full SHA, UI expects short 7-char)
        for release in releases_list:
            git_sha = release.get("git_sha", "")
            if git_sha and len(git_sha) > 7:
                release["git_sha"] = git_sha[:7]

        # Enrich with GitHub API data
        github_token = (
            db.query(Setting).filter(Setting.key == "REPOSITORY_TOKEN").first()
        )

        if github_token and github_token.value and releases_list:
            headers = {
                "Authorization": f"token {github_token.value}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Get app's repo info
            repo_name = app.repo or app_name
            github_org = project.github_org or "cheapaio"

            async with httpx.AsyncClient() as client:
                for release in releases_list:
                    sha = release["git_sha"]
                    if sha and sha != "-" and len(sha) >= 7:
                        try:
                            # Get commit info from GitHub
                            url = f"https://api.github.com/repos/{github_org}/{repo_name}/commits/{sha}"
                            response = await client.get(
                                url, headers=headers, timeout=5.0
                            )

                            if response.status_code == 200:
                                commit_data = response.json()
                                release["commit_message"] = commit_data.get(
                                    "commit", {}
                                ).get("message", "-")
                                release["author"] = {
                                    "login": commit_data.get("author", {}).get(
                                        "login", "unknown"
                                    ),
                                    "avatar_url": commit_data.get("author", {}).get(
                                        "avatar_url", ""
                                    ),
                                }
                            else:
                                release["commit_message"] = "-"
                                release["author"] = None
                        except Exception:
                            release["commit_message"] = "-"
                            release["author"] = None
                    else:
                        release["commit_message"] = "-"
                        release["author"] = None
        else:
            # No GitHub token or no data - add empty fields
            for release in releases_list:
                release["commit_message"] = "-"
                release["author"] = None

        return {"releases": releases_list}

    except RuntimeError as e:
        # CLI execution failed
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/{app_name}/switch")
async def switch_version(
    project_name: str,
    app_name: str,
    request: SwitchVersionRequest,
    db: Session = Depends(get_db),
):
    """
    Switch app to a different version (rollback/rollforward).
    Uses SuperDeploy CLI switch command for zero-downtime deployment.

    Returns:
    - message: Success/failure message
    - git_sha: Version switched to
    """
    try:
        from utils.cli import get_cli

        # Get project
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Use centralized CLI executor
        cli = get_cli()

        # Collect output
        output_lines = []
        async for line in cli.execute(
            f"{project_name}:releases:switch",
            args=["-a", app_name, "-v", request.git_sha, "--force"],
        ):
            output_lines.append(line)

        output = "".join(output_lines)

        return {
            "message": f"Successfully switched to {request.git_sha[:7]}",
            "git_sha": request.git_sha,
            "output": output,
        }

    except RuntimeError as e:
        # CLI execution failed
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
