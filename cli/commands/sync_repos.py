"""SuperDeploy CLI - Sync Repository Secrets"""

import click
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import dotenv_values
from cli.utils import load_env

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--env-dir",
    "-d",
    help="Directory containing app .env files (e.g., /path/to/app-repos)",
)
@click.option(
    "--env-file",
    "-e",
    multiple=True,
    help="Specific .env file(s) to sync (e.g., ../api/.env)",
)
def sync_repos(project, env_dir, env_file):
    """
    Sync app-specific secrets to GitHub repositories

    This syncs app-level secrets like:
    - POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    - RABBITMQ_USER, RABBITMQ_PASSWORD
    - REDIS_PASSWORD
    - APP_SECRET_KEY
    - etc.

    You can provide either:
    - A directory containing .env files (--env-dir)
    - Specific .env files (--env-file, multiple allowed)

    The command will auto-detect which repo each .env belongs to
    based on the directory name or explicit mapping.

    \b
    Examples:
      # Auto-discover from directory
      superdeploy sync:repos -p myproject -d ~/app-repos

      # Specific files
      superdeploy sync:repos -p myproject -e ~/app-repos/api/.env -e ~/app-repos/dashboard/.env

      # Use project's .passwords.yml
      superdeploy sync:repos -p myproject
    """
    from cli.utils import validate_project
    import yaml

    validate_project(project)

    console.print(
        Panel.fit(
            f"[bold cyan]🔄 Repository Secrets Sync[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]Syncing app-specific secrets to GitHub...[/white]",
            border_style="cyan",
        )
    )

    # Load infrastructure env for GitHub org
    infra_env = load_env()
    github_org = infra_env.get("GITHUB_ORG", f"{project}io")

    # Determine env files to process
    env_files_to_sync = []

    if env_file:
        # User provided specific files
        for f in env_file:
            path = Path(f).expanduser().resolve()
            if not path.exists():
                console.print(f"[yellow]⚠️  File not found: {path}[/yellow]")
                continue
            env_files_to_sync.append(path)

    elif env_dir:
        # Auto-discover from directory
        dir_path = Path(env_dir).expanduser().resolve()
        if not dir_path.exists():
            console.print(f"[red]❌ Directory not found: {dir_path}[/red]")
            raise SystemExit(1)

        # Look for .env files in subdirectories
        for subdir in dir_path.iterdir():
            if subdir.is_dir():
                env_path = subdir / ".env"
                if env_path.exists():
                    env_files_to_sync.append(env_path)

    else:
        # Default: Use project's .passwords.yml (local)
        from cli.utils import get_project_root

        project_root = get_project_root()
        project_dir = project_root / "projects" / project
        passwords_file = project_dir / ".passwords.yml"

        if not passwords_file.exists():
            console.print(f"[red]❌ No .passwords.yml found at {passwords_file}[/red]")
            console.print(
                "[yellow]Hint: Provide --env-dir or --env-file, or run 'superdeploy init' first[/yellow]"
            )
            raise SystemExit(1)

        # Load passwords and sync to all services
        try:
            passwords_data = yaml.safe_load(passwords_file.read_text())
            
            # Extract passwords dict (they're nested under 'passwords' key)
            passwords = passwords_data.get("passwords", {})

            # Get services from project config
            project_config = project_dir / "config.yml"
            services = ["api", "dashboard", "services"]  # Default

            if project_config.exists():
                config = yaml.safe_load(project_config.read_text())
                services = config.get("services", services)

            console.print("\n[cyan]📦 Using generated passwords from:[/cyan]")
            console.print(f"  {passwords_file}")
            console.print("\n[cyan]📦 Target repositories:[/cyan]")
            for service in services:
                console.print(f"  • {github_org}/{service}")

            # Prepare secrets
            secrets = {
                "POSTGRES_USER": f"{project}_user",
                "POSTGRES_PASSWORD": passwords.get("POSTGRES_PASSWORD"),
                "POSTGRES_DB": f"{project}_db",
                "POSTGRES_HOST": "postgres",
                "POSTGRES_PORT": "5432",
                "RABBITMQ_USER": f"{project}_user",
                "RABBITMQ_PASSWORD": passwords.get("RABBITMQ_PASSWORD"),
                "RABBITMQ_HOST": "rabbitmq",
                "RABBITMQ_PORT": "5672",
                "REDIS_PASSWORD": passwords.get("REDIS_PASSWORD"),
                "REDIS_HOST": "redis",
                "REDIS_PORT": "6379",
            }

            # Sync to all services
            console.print("\n[cyan]🔄 Syncing secrets...[/cyan]")
            for service in services:
                repo = f"{github_org}/{service}"
                console.print(f"\n  [bold]{repo}[/bold]")

                for key, value in secrets.items():
                    if value is None:
                        console.print(f"    [yellow]⚠[/yellow] {key}: missing value")
                        continue

                    try:
                        subprocess.run(
                            ["gh", "secret", "set", key, "-b", str(value), "-R", repo],
                            check=True,
                            capture_output=True,
                        )
                        console.print(f"    [green]✓[/green] {key}")
                    except subprocess.CalledProcessError as e:
                        console.print(f"    [red]✗[/red] {key}: {e.stderr.decode()}")
                    except Exception as e:
                        console.print(f"    [red]✗[/red] {key}: {e}")

            console.print("\n[green]✅ Repository secrets synced![/green]")
            return

        except Exception as e:
            console.print(f"[red]❌ Error loading passwords: {e}[/red]")
            raise SystemExit(1)

    # Process discovered env files
    if not env_files_to_sync:
        console.print("[yellow]⚠️  No .env files found to sync[/yellow]")
        raise SystemExit(1)

    console.print(f"\n[cyan]📦 Found {len(env_files_to_sync)} .env file(s):[/cyan]")

    # Map env files to repos
    env_to_repo = {}
    for env_path in env_files_to_sync:
        # Try to determine repo name from directory
        repo_name = env_path.parent.name
        env_to_repo[env_path] = f"{github_org}/{repo_name}"
        console.print(f"  • {env_path.name} → {github_org}/{repo_name}")

    # Sync each file
    console.print("\n[cyan]🔄 Syncing secrets...[/cyan]")

    for env_path, repo in env_to_repo.items():
        console.print(f"\n  [bold]{repo}[/bold]")

        # Load env file
        try:
            env_vars = dotenv_values(env_path)
        except Exception as e:
            console.print(f"    [red]✗[/red] Failed to load: {e}")
            continue

        # Sync each secret
        for key, value in env_vars.items():
            if not value or value.startswith("#"):
                continue

            try:
                subprocess.run(
                    ["gh", "secret", "set", key, "-b", value, "-R", repo],
                    check=True,
                    capture_output=True,
                )
                console.print(f"    [green]✓[/green] {key}")
            except subprocess.CalledProcessError as e:
                console.print(f"    [red]✗[/red] {key}: {e.stderr.decode()}")
            except Exception as e:
                console.print(f"    [red]✗[/red] {key}: {e}")

    console.print("\n[green]✅ Repository secrets synced![/green]")
