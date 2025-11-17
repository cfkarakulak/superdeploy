from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Project, App
from pydantic import BaseModel
from cache import get_cache, set_cache, CACHE_TTL

router = APIRouter(tags=["apps"])


class SwitchVersionRequest(BaseModel):
    """Request to switch to a different version."""

    git_sha: str


@router.get("/{project_name}/list")
async def list_apps(project_name: str, db: Session = Depends(get_db)):
    """
    List all apps for a project from database (with Redis cache).

    Database is the master source, not config.yml.
    """
    # Check cache first
    cache_key = f"apps:{project_name}"
    cached = get_cache(cache_key)
    if cached:
        return cached

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
                "repo": app.repo,
                "owner": app.owner,
            }
        )

    response = {"apps": apps_list}

    # Cache for 5 minutes
    set_cache(cache_key, response, CACHE_TTL["apps"])

    return response


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

        # Store full SHAs for GitHub API calls, we'll shorten later
        full_shas = {}
        for release in releases_list:
            git_sha = release.get("git_sha", "")
            if git_sha and git_sha != "-":
                full_shas[git_sha] = git_sha

        # Enrich with GitHub API data (use full SHAs if needed)
        import os

        github_token_value = os.getenv("GITHUB_TOKEN")

        if github_token_value and releases_list:
            headers = {
                "Authorization": f"token {github_token_value}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Get app's repo info
            repo_name = app.repo or app_name
            github_org = project.github_org or "cheapaio"

            async with httpx.AsyncClient() as client:
                for release in releases_list:
                    sha = release.get("git_sha", "")
                    if sha and sha != "-":
                        try:
                            # Get commit info from GitHub (works with both full and short SHAs)
                            url = f"https://api.github.com/repos/{github_org}/{repo_name}/commits/{sha}"
                            response = await client.get(
                                url, headers=headers, timeout=5.0
                            )

                            if response.status_code == 200:
                                commit_data = response.json()
                                # Override with GitHub data if available
                                github_commit_msg = commit_data.get("commit", {}).get(
                                    "message", ""
                                )
                                if github_commit_msg:
                                    release["commit_message"] = github_commit_msg
                                release["author"] = {
                                    "login": commit_data.get("author", {}).get(
                                        "login", "unknown"
                                    ),
                                    "avatar_url": commit_data.get("author", {}).get(
                                        "avatar_url", ""
                                    ),
                                }
                            else:
                                # Keep CLI commit message if GitHub fails
                                if (
                                    not release.get("commit_message")
                                    or release.get("commit_message") == "-"
                                ):
                                    release["commit_message"] = "-"
                                release["author"] = None
                        except Exception:
                            # Keep CLI commit message if GitHub fails
                            if (
                                not release.get("commit_message")
                                or release.get("commit_message") == "-"
                            ):
                                release["commit_message"] = "-"
                            release["author"] = None
                    else:
                        if not release.get("commit_message"):
                            release["commit_message"] = "-"
                        release["author"] = None
        else:
            # No GitHub token - keep CLI data as-is
            for release in releases_list:
                if not release.get("commit_message"):
                    release["commit_message"] = "-"
                if not release.get("author"):
                    release["author"] = None

        # Shorten git SHAs for frontend display (after GitHub API calls)
        for release in releases_list:
            git_sha = release.get("git_sha", "")
            if git_sha and len(git_sha) > 7:
                release["git_sha"] = git_sha[:7]

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

    Streams CLI output in real-time for better UX.

    Returns:
    - StreamingResponse with CLI output
    """
    try:
        from utils.cli import get_cli
        from fastapi.responses import StreamingResponse

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

        # Stream CLI output
        async def generate():
            try:
                async for line in cli.execute(
                    f"{project_name}:releases:switch",
                    args=["-a", app_name, "-v", request.git_sha, "--force"],
                ):
                    yield line
            except RuntimeError as e:
                yield f"\n❌ Error: {str(e)}\n"
            except Exception as e:
                yield f"\n❌ Unexpected error: {str(e)}\n"

        return StreamingResponse(generate(), media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
