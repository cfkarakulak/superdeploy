"""GitHub API routes."""

from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(tags=["github"])


def get_github_token(project_name: str) -> str:
    """Get GitHub token from database."""
    from database import SessionLocal
    from models import Project, Environment, Secret

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        production_env = (
            db.query(Environment)
            .filter(
                Environment.project_id == project.id, Environment.name == "production"
            )
            .first()
        )

        if not production_env:
            raise HTTPException(
                status_code=404, detail="Production environment not found"
            )

        # Try to find GitHub token in secrets (shared or api)
        token_secret = (
            db.query(Secret)
            .filter(
                Secret.environment_id == production_env.id,
                Secret.app == "shared",
                Secret.key == "GITHUB_TOKEN",
            )
            .first()
        )

        if token_secret:
            return token_secret.value

        # Try GH_TOKEN as fallback
        token_secret = (
            db.query(Secret)
            .filter(
                Secret.environment_id == production_env.id,
                Secret.app == "shared",
                Secret.key == "GH_TOKEN",
            )
            .first()
        )

        if token_secret:
            return token_secret.value

        raise HTTPException(status_code=404, detail="GitHub token not found in secrets")

    finally:
        db.close()


def get_github_repo(project_name: str) -> tuple[str, str]:
    """Get GitHub owner and repo from database.

    For now, defaults to 'cheapa-io' organization.
    TODO: Add github_owner field to Project model.
    """
    # Default fallback
    return ("cheapa-io", project_name)


@router.get("/{project_name}/repos/{repo_name}/info")
async def get_repo_info(project_name: str, repo_name: str):
    """Get repository owner and name."""
    try:
        owner, _ = get_github_repo(project_name)
        return {
            "owner": owner,
            "repo": repo_name,
            "full_name": f"{owner}/{repo_name}",
        }
    except Exception:
        # Fallback to cheapa-io
        return {
            "owner": "cheapa-io",
            "repo": repo_name,
            "full_name": f"cheapa-io/{repo_name}",
        }


@router.get("/{project_name}/repos/{repo_name}/workflows")
async def get_repo_workflows(project_name: str, repo_name: str):
    """Get GitHub Actions workflow runs for a specific repo."""
    try:
        from database import SessionLocal
        from models import Project, App

        token = get_github_token(project_name)

        # Get owner and repo from App table
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == repo_name)
                .first()
            )

            if app and app.owner and app.repo:
                owner = app.owner
                repo = app.repo
            else:
                # Fallback
                owner = "cheapaio"
                repo = repo_name
        finally:
            db.close()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={"per_page": 10},
            )

            if response.status_code == 404:
                return {"workflow_runs": [], "total_count": 0}

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

            return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/repos/{repo_name}/runs/{run_id}")
async def get_workflow_run(project_name: str, repo_name: str, run_id: int):
    """Get specific workflow run details."""
    try:
        from database import SessionLocal
        from models import Project, App

        token = get_github_token(project_name)

        # Get owner and repo from App table
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == repo_name)
                .first()
            )

            if app and app.owner and app.repo:
                owner = app.owner
                repo = app.repo
            else:
                owner = "cheapaio"
                repo = repo_name
        finally:
            db.close()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

            return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/repos/{repo_name}/runs/{run_id}/jobs")
async def get_workflow_run_jobs(project_name: str, repo_name: str, run_id: int):
    """Get jobs for a specific workflow run."""
    try:
        from database import SessionLocal
        from models import Project, App

        token = get_github_token(project_name)

        # Get owner and repo from App table
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == repo_name)
                .first()
            )

            if app and app.owner and app.repo:
                owner = app.owner
                repo = app.repo
            else:
                owner = "cheapaio"
                repo = repo_name
        finally:
            db.close()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

            return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/actions")
async def get_github_actions(project_name: str):
    """Get GitHub Actions workflow runs for all apps in project."""
    from database import SessionLocal
    from models import Project, App

    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        apps = db.query(App).filter(App.project_id == project.id).all()

        token = get_github_token(project_name)
        owner, _ = get_github_repo(project_name)

        all_workflows = []

        async with httpx.AsyncClient() as client:
            for app in apps:
                try:
                    response = await client.get(
                        f"https://api.github.com/repos/{owner}/{app.name}/actions/runs",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                        params={"per_page": 5},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        for run in data.get("workflow_runs", []):
                            run["app_name"] = app.name
                            all_workflows.append(run)

                except Exception as e:
                    print(f"Error fetching workflows for {app.name}: {str(e)}")
                    continue

        # Sort by created_at descending
        all_workflows.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {"workflow_runs": all_workflows[:10], "total_count": len(all_workflows)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
