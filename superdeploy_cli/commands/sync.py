import os

"""SuperDeploy CLI - Sync command (AGE key + GitHub secrets automation)"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from superdeploy_cli.utils import load_env, ssh_command, validate_env_vars

console = Console()


def get_age_public_key(env):
    """Fetch AGE public key from runner VM"""
    try:
        # Read entire key file, then parse locally
        key_file = ssh_command(
            host=env["CORE_EXTERNAL_IP"],
            user=env.get("SSH_USER", "superdeploy"),
            key_path=os.path.expanduser(env["SSH_KEY_PATH"]),
            cmd="cat /opt/forgejo-runner/.age/key.txt",
        )

        # Extract public key line (format: "# public key: age1...")
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
            json={
                "name": token_name,
                "scopes": [
                    "read:user",
                    "write:repository",
                    "write:activitypub",
                    "write:misc",
                    "write:organization",
                ],
            },
        )

        if response.status_code == 201:
            pat = response.json()["sha1"]
            console.print("[green]✅ Forgejo PAT created[/green]")
            return pat
        else:
            console.print(f"[yellow]⚠️  PAT creation failed: {response.text}[/yellow]")
            return None
    except Exception as e:
        console.print(f"[yellow]⚠️  PAT creation failed: {e}[/yellow]")
        return None


def set_github_repo_secrets(repo, secrets):
    """Set GitHub repository secrets using gh CLI"""
    console.print(f"[dim]Setting repository secrets for {repo}...[/dim]")

    for key, value in secrets.items():
        try:
            subprocess.run(
                ["gh", "secret", "set", key, "-b", value, "-R", repo],
                check=True,
                capture_output=True,
            )
            console.print(f"  [green]✓[/green] {key}")
        except subprocess.CalledProcessError as e:
            console.print(f"  [red]✗[/red] {key}: {e.stderr.decode()}")


def create_github_environment(repo, env_name):
    """Create GitHub environment if it doesn't exist"""
    try:
        # Check if environment exists
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/environments/{env_name}"],
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            # Create environment (minimal, free plan compatible)
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/environments/{env_name}",
                    "-X",
                    "PUT",
                ],
                check=True,
                capture_output=True,
            )
            console.print(f"  [green]✓[/green] Created environment: {env_name}")
        else:
            console.print(f"  [dim]Environment '{env_name}' already exists[/dim]")

        return True
    except subprocess.CalledProcessError as e:
        console.print(
            f"  [red]✗[/red] Failed to create environment: {e.stderr.decode()}"
        )
        return False


def set_github_env_secrets(repo, env_name, secrets):
    """Set GitHub environment secrets using gh CLI"""
    console.print(f"[dim]Setting environment secrets for {repo} ({env_name})...[/dim]")

    for key, value in secrets.items():
        try:
            subprocess.run(
                ["gh", "secret", "set", key, "-b", value, "-e", env_name, "-R", repo],
                check=True,
                capture_output=True,
            )
            console.print(f"  [green]✓[/green] {key}")
        except subprocess.CalledProcessError as e:
            console.print(f"  [red]✗[/red] {key}: {e.stderr.decode()}")


@click.command()
@click.option("--skip-forgejo", is_flag=True, help="Skip Forgejo PAT creation")
@click.option("--skip-github", is_flag=True, help="Skip GitHub secrets sync")
def sync(skip_forgejo, skip_github):
    """
    Sync ALL secrets to GitHub (magic!)

    This command will:
    - Fetch AGE public key from runner VM
    - Create Forgejo PAT (if needed)
    - Push ALL secrets to GitHub repos (using gh CLI)

    \b
    Requirements:
    - gh CLI installed and authenticated
    - SSH access to VMs
    - GITHUB_TOKEN in .env
    """
    console.print(
        Panel.fit(
            "[bold cyan]🔄 SuperDeploy Secret Sync[/bold cyan]\n\n"
            "[white]Automating GitHub secrets configuration...[/white]",
            border_style="cyan",
        )
    )

    env = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "GITHUB_TOKEN"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    # GitHub repos (from .env or defaults)
    repos = {
        "api": env.get("GITHUB_REPO_API", "cheapaio/api"),
        "dashboard": env.get("GITHUB_REPO_DASHBOARD", "cheapaio/dashboard"),
        "services": env.get("GITHUB_REPO_SERVICES", "cheapaio/services"),
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Fetch AGE public key
        task1 = progress.add_task("[cyan]Fetching AGE public key from VM...", total=1)
        age_public_key = get_age_public_key(env)

        if not age_public_key:
            console.print("[red]❌ Failed to fetch AGE public key![/red]")
            raise SystemExit(1)

        progress.advance(task1)
        console.print(f"[green]✅ AGE Public Key: {age_public_key[:30]}...[/green]")

        # Step 2: Create Forgejo PAT (if not exists)
        task2 = progress.add_task("[cyan]Creating Forgejo PAT...", total=1)

        forgejo_pat = env.get("FORGEJO_PAT")
        if not forgejo_pat or forgejo_pat == "auto-generated" or skip_forgejo:
            forgejo_pat = create_forgejo_pat(env)

            if forgejo_pat:
                # Update .env file
                env_file_path = env.get("ENV_FILE_PATH", ".env")
                with open(env_file_path, "r") as f:
                    lines = f.readlines()

                with open(env_file_path, "w") as f:
                    for line in lines:
                        if line.startswith("FORGEJO_PAT="):
                            f.write(f"FORGEJO_PAT={forgejo_pat}\n")
                        else:
                            f.write(line)

                console.print("[green]✅ Forgejo PAT saved to .env[/green]")

        progress.advance(task2)

        if skip_github:
            console.print("[yellow]⚠️  Skipping GitHub secrets sync[/yellow]")
            return

        # Step 3: Sync to GitHub
        task3 = progress.add_task(
            "[cyan]Syncing secrets to GitHub...", total=len(repos)
        )

        for app_name, repo in repos.items():
            console.print(
                f"\n[bold cyan]━━━ {app_name.upper()} ({repo}) ━━━[/bold cyan]"
            )

            # Repository secrets (infrastructure/build related)
            repo_secrets = {
                "AGE_PUBLIC_KEY": age_public_key,
                "FORGEJO_BASE_URL": f"http://{env['CORE_EXTERNAL_IP']}:3001",
                "FORGEJO_ORG": env.get("FORGEJO_ORG", "cradexco"),
                "FORGEJO_PAT": forgejo_pat or "",
                "DOCKER_USERNAME": env.get("DOCKER_USERNAME", ""),
                "DOCKER_TOKEN": env.get("DOCKER_TOKEN", ""),
            }

            set_github_repo_secrets(repo, repo_secrets)

            # Environment-specific secrets (production & staging)
            for env_name in ["production", "staging"]:
                console.print(f"\n[dim]Configuring {env_name} environment...[/dim]")

                # Create environment
                if not create_github_environment(repo, env_name):
                    console.print(f"[yellow]⚠️  Skipping {env_name} secrets[/yellow]")
                    continue

                # Environment secrets - use actual .env values
                env_secrets = {
                    "POSTGRES_HOST": env.get("CORE_INTERNAL_IP", ""),
                    "POSTGRES_USER": env.get("POSTGRES_USER"),
                    "POSTGRES_PASSWORD": env.get("POSTGRES_PASSWORD"),
                    "POSTGRES_DB": env.get("POSTGRES_DB"),
                    "POSTGRES_PORT": "5432",
                    "RABBITMQ_HOST": env.get("CORE_INTERNAL_IP", ""),
                    "RABBITMQ_USER": env.get("RABBITMQ_USER"),
                    "RABBITMQ_PASSWORD": env.get("RABBITMQ_PASSWORD"),
                    "RABBITMQ_PORT": "5672",
                    "REDIS_HOST": env.get("CORE_INTERNAL_IP", ""),
                    "REDIS_PASSWORD": env.get("REDIS_PASSWORD", ""),
                    "API_SECRET_KEY": env.get("API_SECRET_KEY", ""),
                    "API_DEBUG": "true" if env_name == "staging" else "false",
                    "API_BASE_URL": f"http://{env.get('CORE_EXTERNAL_IP', '')}:8000",
                    "PUBLIC_URL": f"http://{env.get('CORE_EXTERNAL_IP', '')}",
                    "SENTRY_DSN": env.get("SENTRY_DSN", ""),
                }

                set_github_env_secrets(repo, env_name, env_secrets)

            progress.advance(task3)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Sync Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("\n[white]Next steps:[/white]")
    console.print("  1. Push to GitHub: [cyan]git push origin production[/cyan]")
    console.print("  2. Deployment will auto-trigger!")
    console.print("\n[dim]All secrets have been configured automatically.[/dim]")
