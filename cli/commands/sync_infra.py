"""SuperDeploy CLI - Sync Infrastructure Secrets"""

import os
import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from cli.utils import load_env, ssh_command, validate_env_vars

console = Console()


def get_age_public_key(env):
    """Fetch AGE public key from runner VM"""
    try:
        key_file = ssh_command(
            host=env["CORE_EXTERNAL_IP"],
            user=env.get("SSH_USER", "superdeploy"),
            key_path=os.path.expanduser(env["SSH_KEY_PATH"]),
            cmd="cat /opt/forgejo-runner/.age/key.txt",
        )

        for line in key_file.split("\n"):
            if "public key:" in line:
                return line.split("public key:")[-1].strip()

        console.print("[red]❌ Could not find public key in AGE key file[/red]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Failed to fetch AGE key: {e}[/red]")
        return None


def create_forgejo_pat(env):
    """Create Forgejo Personal Access Token"""
    console.print("[dim]Creating Forgejo PAT...[/dim]")

    import requests
    import time

    forgejo_url = f"http://{env['CORE_EXTERNAL_IP']}:3001"
    token_name = f"github-actions-{int(time.time())}"

    try:
        response = requests.post(
            f"{forgejo_url}/api/v1/users/{env['FORGEJO_ADMIN_USER']}/tokens",
            auth=(env["FORGEJO_ADMIN_USER"], env["FORGEJO_ADMIN_PASSWORD"]),
            json={"name": token_name, "scopes": ["write:repository", "write:user"]},
            timeout=10,
        )

        if response.status_code == 201:
            token = response.json()["sha1"]
            console.print("[green]✓[/green] Forgejo PAT created")
            return token
        else:
            console.print(f"[red]✗[/red] Failed: {response.text}")
            return None

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        return None


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
def sync_infra(project):
    """
    Sync infrastructure secrets to GitHub repositories

    This syncs ONLY infrastructure-level secrets:
    - FORGEJO_BASE_URL
    - FORGEJO_PAT
    - AGE_PUBLIC_KEY
    - CORE_EXTERNAL_IP
    - DOCKER_USERNAME
    - DOCKER_TOKEN

    These are needed for GitHub Actions to trigger Forgejo deployments.

    \b
    Example:
      superdeploy sync:infra -p myproject
    """
    from cli.utils import validate_project

    validate_project(project)

    console.print(
        Panel.fit(
            f"[bold cyan]🔄 Infrastructure Secrets Sync[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]Syncing infrastructure secrets to GitHub...[/white]",
            border_style="cyan",
        )
    )

    # Load infrastructure env
    env = load_env()

    # Validate required vars
    required = [
        "CORE_EXTERNAL_IP",
        "SSH_KEY_PATH",
        "FORGEJO_ADMIN_USER",
        "FORGEJO_ADMIN_PASSWORD",
        "DOCKER_USERNAME",
        "DOCKER_TOKEN",
        "GITHUB_ORG",
    ]

    missing = validate_env_vars(env, required)
    if missing:
        console.print(f"[red]❌ Missing env vars: {', '.join(missing)}[/red]")
        raise SystemExit(1)

    # Get GitHub org and repos
    github_org = env.get("GITHUB_ORG", f"{project}io")

    # Determine which repos to sync to
    # Read from project config if exists (local)
    from pathlib import Path
    from cli.utils import get_project_root
    import yaml

    project_root = get_project_root()
    project_dir = project_root / "projects" / project
    project_config = project_dir / "config.yml"
    services = ["api", "dashboard", "services"]  # Default

    if project_config.exists():
        try:
            config = yaml.safe_load(project_config.read_text())
            services = config.get("services", services)
        except:
            pass

    console.print("\n[cyan]📦 Target repositories:[/cyan]")
    for service in services:
        console.print(f"  • {github_org}/{service}")

    # Step 1: Fetch AGE public key
    console.print("\n[cyan]1️⃣ Fetching AGE public key from runner...[/cyan]")
    age_public_key = get_age_public_key(env)
    if not age_public_key:
        console.print("[red]❌ Failed to get AGE key[/red]")
        raise SystemExit(1)
    console.print(f"[green]✓[/green] AGE key: {age_public_key[:20]}...")

    # Step 2: Create Forgejo PAT
    console.print("\n[cyan]2️⃣ Creating Forgejo PAT...[/cyan]")
    forgejo_pat = create_forgejo_pat(env)
    if not forgejo_pat:
        console.print("[red]❌ Failed to create Forgejo PAT[/red]")
        raise SystemExit(1)
    console.print("[green]✓[/green] PAT created")

    # Step 3: Sync to GitHub
    console.print("\n[cyan]3️⃣ Syncing to GitHub repositories...[/cyan]")

    infra_secrets = {
        "FORGEJO_BASE_URL": f"http://{env['CORE_EXTERNAL_IP']}:3001",
        "FORGEJO_PAT": forgejo_pat,
        "AGE_PUBLIC_KEY": age_public_key,
        "CORE_EXTERNAL_IP": env["CORE_EXTERNAL_IP"],
        "DOCKER_USERNAME": env["DOCKER_USERNAME"],
        "DOCKER_TOKEN": env["DOCKER_TOKEN"],
    }

    for service in services:
        repo = f"{github_org}/{service}"
        console.print(f"\n  [bold]{repo}[/bold]")

        for key, value in infra_secrets.items():
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

    console.print("\n[green]✅ Infrastructure secrets synced![/green]")
    console.print(
        "\n[dim]Next: Run 'superdeploy sync:repos' to sync app-specific secrets[/dim]"
    )
