"""GitHub API routes."""

from fastapi import APIRouter, HTTPException
import os
from pathlib import Path
import yaml

router = APIRouter(tags=["github"])

import httpx


def get_github_token(project_name: str) -> str:
    """Get GitHub token from project secrets."""
    secrets_path = (
        Path(__file__).parent.parent.parent.parent
        / "projects"
        / project_name
        / "secrets.yml"
    )

    if not secrets_path.exists():
        raise HTTPException(status_code=404, detail="Project secrets not found")

    with open(secrets_path, "r") as f:
        secrets = yaml.safe_load(f)

    # Try to find GitHub token in secrets
    if secrets and "secrets" in secrets:
        project_secrets = secrets["secrets"]

        # Check in shared secrets
        if "shared" in project_secrets:
            if "GITHUB_TOKEN" in project_secrets["shared"]:
                return project_secrets["shared"]["GITHUB_TOKEN"]
            if "GH_TOKEN" in project_secrets["shared"]:
                return project_secrets["shared"]["GH_TOKEN"]

        # Check in api secrets
        if "api" in project_secrets:
            if "GITHUB_TOKEN" in project_secrets["api"]:
                return project_secrets["api"]["GITHUB_TOKEN"]
            if "GH_TOKEN" in project_secrets["api"]:
                return project_secrets["api"]["GH_TOKEN"]

    # Fallback to environment variable
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise HTTPException(status_code=404, detail="GitHub token not found")

    return token


def get_github_repo(project_name: str) -> tuple[str, str]:
    """Get GitHub owner and repo from project config."""
    config_path = (
        Path(__file__).parent.parent.parent.parent
        / "projects"
        / project_name
        / "config.yml"
    )

    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Project config not found")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if not config or "github" not in config:
        raise HTTPException(status_code=404, detail="GitHub config not found")

    github_config = config["github"]

    # Try to get owner/repo or fallback to organization + project name
    owner = github_config.get("owner") or github_config.get("organization")
    repo = github_config.get("repo") or project_name

    if not owner:
        raise HTTPException(
            status_code=404, detail="GitHub owner/organization not configured"
        )

    return owner, repo


@router.get("/actions/{project_name}")
async def get_github_actions(project_name: str):
    """Get GitHub Actions workflow runs for a project (aggregated from all app repos)."""
    import httpx
    import yaml

    try:
        token = get_github_token(project_name)
        owner, _ = get_github_repo(project_name)

        # Load project config to get apps
        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "projects"
            / project_name
            / "config.yml"
        )
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        apps = config.get("apps", {})

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        all_runs = []

        # Fetch workflow runs from each app repo
        async with httpx.AsyncClient() as client:
            for app_name in apps.keys():
                url = f"https://api.github.com/repos/{owner}/{app_name}/actions/runs"
                params = {"per_page": 10, "page": 1}

                try:
                    response = await client.get(
                        url, headers=headers, params=params, timeout=10.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        runs = data.get("workflow_runs", [])
                        # Add app name to each run for context
                        for run in runs:
                            run["app"] = app_name
                        all_runs.extend(runs)
                except Exception as e:
                    print(f"Failed to fetch runs for {app_name}: {e}")
                    continue

        # Sort by created_at (most recent first)
        all_runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Limit to 20 most recent
        all_runs = all_runs[:20]

        return {
            "workflow_runs": all_runs,
            "total_count": len(all_runs),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Return empty list if GitHub is not configured
        print(f"GitHub Actions error: {e}")
        return {"workflow_runs": [], "total_count": 0, "error": str(e)}


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
        token = get_github_token(project_name)
        owner, _ = get_github_repo(project_name)

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs"
        params = {"per_page": 20, "page": 1}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=headers, params=params, timeout=10.0
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


@router.get("/actions/{project_name}/{run_id}")
async def get_workflow_run(project_name: str, run_id: int):
    """Get details of a specific workflow run."""
    try:
        token = get_github_token(project_name)
        owner, repo = get_github_repo(project_name)

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)

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
