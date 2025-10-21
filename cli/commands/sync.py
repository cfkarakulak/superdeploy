import os

"""SuperDeploy CLI - Sync command (AGE key + GitHub secrets automation)"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.utils import load_env, ssh_command, validate_env_vars

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


def sync_forgejo_secrets(env, forgejo_pat, project_env=None):
    """Sync all secrets to Forgejo repository"""
    import requests

    forgejo_url = f"http://{env['CORE_EXTERNAL_IP']}:3001"
    org = env["FORGEJO_ORG"]  # No fallback - MUST exist
    repo = env["REPO_SUPERDEPLOY"]  # No fallback - MUST exist

    # Test connection first
    try:
        test_response = requests.get(
            f"{forgejo_url}/api/v1/user",
            headers={"Authorization": f"token {forgejo_pat}"},
            timeout=5,
        )
        if test_response.status_code != 200:
            console.print(
                "[yellow]⚠️  Forgejo not ready yet (will sync on next run)[/yellow]"
            )
            return
    except Exception as e:
        console.print(f"[yellow]⚠️  Forgejo not accessible: {e}[/yellow]")
        return

    # Merge project-specific secrets if provided
    merged_env = {**env}
    if project_env:
        merged_env.update(project_env)

    secrets = {
        # Core Services (from project secrets)
        "POSTGRES_HOST": merged_env.get(
            "POSTGRES_HOST", env.get("CORE_INTERNAL_IP", "")
        ),
        "POSTGRES_USER": merged_env.get("POSTGRES_USER", ""),
        "POSTGRES_PASSWORD": merged_env.get("POSTGRES_PASSWORD", ""),
        "POSTGRES_DB": merged_env.get("POSTGRES_DB", ""),
        "POSTGRES_PORT": "5432",
        "RABBITMQ_HOST": merged_env.get(
            "RABBITMQ_HOST", env.get("CORE_INTERNAL_IP", "")
        ),
        "RABBITMQ_USER": merged_env.get("RABBITMQ_USER", ""),
        "RABBITMQ_PASSWORD": merged_env.get("RABBITMQ_PASSWORD", ""),
        "RABBITMQ_PORT": "5672",
        "REDIS_HOST": merged_env.get("REDIS_HOST", env.get("CORE_INTERNAL_IP", "")),
        "REDIS_PASSWORD": merged_env.get("REDIS_PASSWORD", ""),
        # App Config
        "API_SECRET_KEY": merged_env.get("API_SECRET_KEY", ""),
        "API_DEBUG": "false",
        "API_BASE_URL": f"http://{env['CORE_EXTERNAL_IP']}:8000",
        "PUBLIC_URL": f"http://{env['CORE_EXTERNAL_IP']}",
        "SENTRY_DSN": merged_env.get("SENTRY_DSN", ""),  # Optional
        # Infrastructure
        "CORE_EXTERNAL_IP": env["CORE_EXTERNAL_IP"],
        "CORE_INTERNAL_IP": env["CORE_INTERNAL_IP"],
        "DOCKER_REGISTRY": "docker.io",
        "DOCKER_ORG": env["DOCKER_ORG"],
        # Notifications
        "ALERT_EMAIL": env.get("ALERT_EMAIL", ""),  # Optional
        "FORGEJO_ORG": env["FORGEJO_ORG"],
    }

    for key, value in secrets.items():
        try:
            response = requests.put(
                f"{forgejo_url}/api/v1/repos/{org}/{repo}/actions/secrets/{key}",
                headers={
                    "Authorization": f"token {forgejo_pat}",
                    "Content-Type": "application/json",
                },
                json={"data": value},
                timeout=10,
            )
            if response.status_code in [200, 201, 204]:
                console.print(f"  [green]✓[/green] {key}")
            else:
                console.print(f"  [yellow]⚠[/yellow] {key}: {response.status_code}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {key}: {e}")

    console.print("[green]✅ Forgejo secrets synced![/green]")


@click.command()
@click.option("--project", "-p", required=True, help="Project name (e.g., cheapa)")
@click.option("--skip-forgejo", is_flag=True, help="Skip Forgejo PAT creation")
@click.option("--skip-github", is_flag=True, help="Skip GitHub secrets sync")
@click.option(
    "--env-file",
    "-e",
    multiple=True,
    help="Additional .env files to load (e.g., ../my-api/.env)",
)
def sync(project, skip_forgejo, skip_github, env_file):
    """
    Sync ALL secrets to GitHub (magic!)

    This command will:
    - Load secrets from superdeploy/.env (infrastructure)
    - Load secrets from --env-file (app-specific, multiple allowed)
    - Fetch AGE public key from runner VM
    - Create Forgejo PAT (if needed)
    - Push ALL secrets to GitHub repos (using gh CLI)

    \b
    Example:
      superdeploy sync -p cheapa -e ../my-api/.env -e ../my-dashboard/.env

    \b
    Requirements:
    - gh CLI installed and authenticated
    - SSH access to VMs
    """
    from cli.utils import validate_project, get_project_path
    from dotenv import dotenv_values

    # Validate project first
    validate_project(project)
    project_path = get_project_path(project)

    console.print(
        Panel.fit(
            f"[bold cyan]🔄 SuperDeploy Secret Sync[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]Automating GitHub secrets configuration...[/white]",
            border_style="cyan",
        )
    )

    # Load infrastructure .env
    env = load_env()

    # Load additional env files (from CLI args)
    additional_envs = {}
    for env_path in env_file:
        env_path = os.path.expanduser(env_path)
        if os.path.exists(env_path):
            file_envs = dotenv_values(env_path)
            additional_envs.update(file_envs)
            console.print(f"[dim]✓ Loaded: {env_path}[/dim]")
        else:
            console.print(f"[yellow]⚠️  Skipped (not found): {env_path}[/yellow]")
    
    # Load project-specific secrets (OPTIONAL - if exists)
    secrets_file = project_path / "secrets.env"
    project_secrets = {}
    
    if secrets_file.exists():
        project_secrets = dotenv_values(secrets_file)
        console.print(f"[dim]✓ Loaded project secrets: {secrets_file}[/dim]")
    
    # Merge all: infra → project → additional
    env.update(project_secrets)
    env.update(additional_envs)

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    # Check if gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(
            "[yellow]⚠️  GitHub CLI (gh) not installed - skipping GitHub secrets sync[/yellow]"
        )
        console.print("[dim]Install: brew install gh[/dim]")
        skip_github = True

    # Load project config
    import yaml

    config_file = project_path / "config.yml"
    if not config_file.exists():
        console.print(f"[red]✗[/red] Project config not found: {config_file}")
        console.print(f"[yellow]Create config.yml for project '{project}'[/yellow]")
        raise SystemExit(1)

    with open(config_file) as f:
        project_config = yaml.safe_load(f)

    # GitHub repos from project config
    repos = project_config.get("repositories", {})

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

        # Step 2.5: Sync secrets to Forgejo repository
        if forgejo_pat:
            console.print(
                "\n[bold cyan]📝 Syncing secrets to Forgejo repository...[/bold cyan]"
            )
            sync_forgejo_secrets(env, forgejo_pat, project_secrets)

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
                "FORGEJO_ORG": env["FORGEJO_ORG"],
                "FORGEJO_PAT": forgejo_pat,
                "DOCKER_USERNAME": env["DOCKER_USERNAME"],
                "DOCKER_TOKEN": env["DOCKER_TOKEN"],
            }

            set_github_repo_secrets(repo, repo_secrets)

            # Environment-specific secrets (production & staging)
            for env_name in ["production", "staging"]:
                console.print(f"\n[dim]Configuring {env_name} environment...[/dim]")

                # Create environment
                if not create_github_environment(repo, env_name):
                    console.print(f"[yellow]⚠️  Skipping {env_name} secrets[/yellow]")
                    continue

                # Environment secrets - merge infrastructure + project secrets
                merged_env = {**env, **project_secrets}

                env_secrets = {
                    "POSTGRES_HOST": merged_env.get(
                        "POSTGRES_HOST", env["CORE_INTERNAL_IP"]
                    ),
                    "POSTGRES_USER": merged_env.get("POSTGRES_USER", ""),
                    "POSTGRES_PASSWORD": merged_env.get("POSTGRES_PASSWORD", ""),
                    "POSTGRES_DB": merged_env.get("POSTGRES_DB", ""),
                    "POSTGRES_PORT": "5432",
                    "RABBITMQ_HOST": merged_env.get(
                        "RABBITMQ_HOST", env["CORE_INTERNAL_IP"]
                    ),
                    "RABBITMQ_USER": merged_env.get("RABBITMQ_USER", ""),
                    "RABBITMQ_PASSWORD": merged_env.get("RABBITMQ_PASSWORD", ""),
                    "RABBITMQ_PORT": "5672",
                    "REDIS_HOST": merged_env.get("REDIS_HOST", env["CORE_INTERNAL_IP"]),
                    "REDIS_PASSWORD": merged_env.get("REDIS_PASSWORD", ""),
                    "API_SECRET_KEY": merged_env.get("API_SECRET_KEY", ""),
                    "API_DEBUG": "true" if env_name == "staging" else "false",
                    "API_BASE_URL": f"http://{env['CORE_EXTERNAL_IP']}:8000",
                    "PUBLIC_URL": f"http://{env['CORE_EXTERNAL_IP']}",
                    "SENTRY_DSN": merged_env.get("SENTRY_DSN", ""),  # Optional
                    "SMTP_USERNAME": env.get("SMTP_USERNAME", ""),
                    "SMTP_PASSWORD": env.get("SMTP_PASSWORD", ""),
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
