"""GitHub API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(tags=["github"])


def get_github_token(project_name: str) -> str | None:
    """Get GitHub token from database.

    Returns None if no token is configured.
    """
    try:
        from database import SessionLocal
        from models import Secret, Project

        db = SessionLocal()
        try:
            # Get project ID first
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                return None

            # Try GITHUB_TOKEN first
            token_secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project.id,
                    Secret.app_id.is_(None),  # Shared secret
                    Secret.key == "GITHUB_TOKEN",
                    Secret.environment == "production",
                )
                .first()
            )

            if token_secret:
                return token_secret.value

            # Fallback to REPOSITORY_TOKEN
            token_secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project.id,
                    Secret.app_id.is_(None),  # Shared secret
                    Secret.key == "REPOSITORY_TOKEN",
                    Secret.environment == "production",
                )
                .first()
            )

            if token_secret:
                return token_secret.value

            return None
        finally:
            db.close()
    except:
        return None


def get_github_repo(project_name: str) -> tuple[str, str]:
    """Get GitHub owner and repo from database.

    Returns (github_org, project_name) from Project table.
    Raises HTTPException if project not found or github_org not configured.
    """
    try:
        from database import SessionLocal
        from models import Project

        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                raise HTTPException(
                    status_code=404, detail=f"Project '{project_name}' not found"
                )

            if not project.github_org:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project '{project_name}' has no github_org configured",
                )

            return (project.github_org, project_name)
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        if not token:
            return {"workflow_runs": [], "total_count": 0}

        # Get owner and repo from App table (database is source of truth)
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
                # Fallback to GitHub org from project (must be configured)
                if not project.github_org:
                    raise HTTPException(
                        status_code=400,
                        detail=f"App '{repo_name}' has no owner/repo configured and project has no github_org",
                    )
                owner = project.github_org
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
        if not token:
            raise HTTPException(status_code=503, detail="GitHub token not configured")

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
                # Fallback to GitHub org from project (must be configured)
                if not project.github_org:
                    raise HTTPException(
                        status_code=400,
                        detail=f"App '{repo_name}' has no owner/repo configured and project has no github_org",
                    )
                owner = project.github_org
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
        if not token:
            raise HTTPException(status_code=503, detail="GitHub token not configured")

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
                # Fallback to GitHub org from project (must be configured)
                if not project.github_org:
                    raise HTTPException(
                        status_code=400,
                        detail=f"App '{repo_name}' has no owner/repo configured and project has no github_org",
                    )
                owner = project.github_org
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
        if not token:
            return {"workflow_runs": [], "total_count": 0}

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
