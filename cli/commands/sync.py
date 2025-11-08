"""SuperDeploy CLI - Sync command (GitHub secrets automation)"""

import click
import subprocess
import json
from pathlib import Path
from rich.console import Console
from cli.ui_components import show_header
from cli.utils import get_project_root

console = Console()


def read_env_file(env_path):
    """Read .env file and return as dictionary"""
    env_dict = {}
    
    if not env_path.exists():
        return env_dict
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_dict[key] = value
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not read .env file: {e}[/yellow]")
    
    return env_dict


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
        console.print("Add to config.yml:")
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
        console.print(f"[cyan]Environment '{env_name}' (merged .env + secrets.yml):[/cyan]")

        # Read app's local .env file
        app_path = Path(app_config["path"]).expanduser().resolve()
        env_file_path = app_path / ".env"
        
        local_env = {}
        if env_file_path.exists():
            local_env = read_env_file(env_file_path)
            console.print(f"  [dim]📄 Read {len(local_env)} variables from .env[/dim]")
        else:
            console.print(f"  [dim]⚠️  No .env file found at {env_file_path}[/dim]")

        # Get app-specific secrets from secrets.yml
        app_secrets = secret_mgr.get_app_secrets(app_name)
        console.print(f"  [dim]🔐 Read {len(app_secrets)} secrets from secrets.yml[/dim]")

        # MERGE: local .env as base, secrets.yml overrides
        merged_env = {**local_env, **app_secrets}
        console.print(f"  [dim]🔀 Merged total: {len(merged_env)} variables[/dim]")

        # Create JSON secret with merged environment
        env_json_secret_name = f"{app_name.upper()}_ENV_JSON"
        env_json_value = json.dumps(merged_env)
        
        # Add JSON secret to repo secrets
        repo_secrets_with_json = {
            **repo_secrets,
            env_json_secret_name: env_json_value
        }
        
        console.print(f"  [green]✓[/green] {env_json_secret_name} [dim](JSON with {len(merged_env)} vars)[/dim]")

        # Set the JSON secret
        try:
            subprocess.run(
                ["gh", "secret", "set", env_json_secret_name, "-b", env_json_value, "-R", repo],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to set {env_json_secret_name}: {e}")

        console.print()

    console.print("\n[green]✅ Sync complete![/green]")
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("\n1. Get GitHub runner token:")
    console.print(f"   https://github.com/{github_org}/settings/actions/runners/new")
    console.print("\n2. Deploy with token:")
    console.print(f"   [red]GITHUB_RUNNER_TOKEN=<token> superdeploy {project}:up[/red]")
