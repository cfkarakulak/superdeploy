"""SuperDeploy CLI - Sync command (GitHub secrets automation)"""

import click
import subprocess
from rich.console import Console
from cli.ui_components import show_header
from cli.utils import get_project_root

console = Console()


def set_github_repo_secrets(repo, secrets_dict, console):
    """Set GitHub repository secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for key, value in secrets_dict.items():
        try:
            result = subprocess.run(
                ["gh", "secret", "set", key, "-b", str(value), "-R", repo],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [green]✓[/green] {key}")
            success_count += 1
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗[/red] {key}: timeout (30s)")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


def set_github_env_secrets(repo, env_name, secrets_dict, console):
    """Set GitHub environment secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for key, value in secrets_dict.items():
        if not value or str(value).strip() == "":
            continue

        try:
            result = subprocess.run(
                [
                    "gh",
                    "secret",
                    "set",
                    key,
                    "-b",
                    str(value),
                    "-e",
                    env_name,
                    "-R",
                    repo,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [green]✓[/green] {key}")
            success_count += 1
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗[/red] {key}: timeout (30s)")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


@click.command(name="sync")
@click.option("--project", "-p", required=True, help="Project name")
def sync(project):
    """
    Sync ALL secrets to GitHub

    - Repository secrets (Docker, GitHub runner token, etc.)
    - Environment secrets (per-app configuration)

    Requirements:
    - gh CLI installed and authenticated
    - secrets.yml file in project directory

    Example:
        superdeploy cheapa:sync
    """
    show_header(
        title="Sync Secrets to GitHub",
        project=project,
        subtitle="Automated secret management",
        console=console,
    )

    from cli.core.config_loader import ConfigLoader
    from cli.secret_manager import SecretManager

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    # Load config
    config_loader = ConfigLoader(projects_dir)
    try:
        project_config = config_loader.load_project(project)
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        return
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        return

    config = project_config.raw_config

    # Load secrets
    secret_mgr = SecretManager(project_root, project)
    if not secret_mgr.secrets_file.exists():
        console.print("[red]❌ No secrets.yml found![/red]")
        return

    all_secrets = secret_mgr.load_secrets()
    
    # Get GitHub organization from config (NO DEFAULT - must be configured)
    github_org = config.get("github", {}).get("organization")
    if not github_org:
        console.print("[red]❌ GitHub organization not configured![/red]")
        console.print("")
        console.print("Add to project.yml:")
        console.print("[dim]github:")
        console.print("  organization: your-github-org[/dim]")
        console.print("")
        return

    # Check gh CLI
    try:
        subprocess.run(["gh", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]❌ gh CLI not found![/red]")
        console.print("Install: https://cli.github.com/")
        return

    console.print("\n[bold cyan]📦 Repository Secrets[/bold cyan]")
    console.print("[dim]These secrets are shared across all apps in the repo[/dim]\n")

    # Process each app
    for app_name, app_config in config.get("apps", {}).items():
        repo = f"{github_org}/{app_name}"
        console.print(f"[cyan]{repo}:[/cyan]")

        # Repository-level secrets (Docker, orchestrator, etc.)
        repo_secrets = {
            "DOCKER_REGISTRY": all_secrets.get("shared", {}).get(
                "DOCKER_REGISTRY", "docker.io"
            ),
            "DOCKER_ORG": all_secrets.get("shared", {}).get("DOCKER_ORG"),
            "DOCKER_USERNAME": all_secrets.get("shared", {}).get("DOCKER_USERNAME"),
            "DOCKER_TOKEN": all_secrets.get("shared", {}).get("DOCKER_TOKEN"),
        }

        # Remove None values
        repo_secrets = {k: v for k, v in repo_secrets.items() if v is not None}

        success, fail = set_github_repo_secrets(repo, repo_secrets, console)
        console.print(f"  [dim]→ {success} success, {fail} failed[/dim]\n")

        # Environment secrets (production)
        env_name = "production"
        console.print(f"[cyan]Environment '{env_name}':[/cyan]")

        # Get app-specific secrets
        app_secrets = secret_mgr.get_app_secrets(app_name)

        # Create environment if needed
        try:
            subprocess.run(
                ["gh", "api", f"repos/{repo}/environments/{env_name}", "-X", "PUT"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # Environment might already exist

        success, fail = set_github_env_secrets(repo, env_name, app_secrets, console)
        console.print(f"  [dim]→ {success} success, {fail} failed[/dim]\n")

    console.print("\n[green]✅ Sync complete![/green]")
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("\n1. Get GitHub runner token:")
    console.print(f"   https://github.com/{github_org}/settings/actions/runners/new")
    console.print("\n2. Deploy with token:")
    console.print(f"   [red]GITHUB_RUNNER_TOKEN=<token> superdeploy {project}:up[/red]")
