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

    success_count = 0
    fail_count = 0

    for key, value in secrets.items():
        # Skip empty values
        if not value or value == "":
            console.print(f"  [dim]⊘[/dim] {key} (empty, skipped)")
            continue

        try:
            result = subprocess.run(
                ["gh", "secret", "set", key, "-b", value, "-R", repo],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"  [green]✓[/green] {key}")
            success_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {key}: {str(e)}")
            fail_count += 1

    console.print(f"[dim]  → {success_count} success, {fail_count} failed[/dim]")


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

    success_count = 0
    fail_count = 0

    for key, value in secrets.items():
        # Skip empty values (GitHub doesn't accept empty secrets)
        if not value or value == "":
            console.print(f"  [dim]⊘[/dim] {key} (empty, skipped)")
            continue

        console.print(f"  [dim]→ Setting {key}...[/dim]", end="")
        try:
            result = subprocess.run(
                ["gh", "secret", "set", key, "-b", value, "-e", env_name, "-R", repo],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"\r  [green]✓[/green] {key}                    ")
            success_count += 1
        except subprocess.TimeoutExpired:
            console.print(f"\r  [red]✗[/red] {key}: timeout (30s)")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            console.print(f"\r  [red]✗[/red] {key}: {error_msg[:50]}")
            fail_count += 1
        except Exception as e:
            console.print(f"\r  [red]✗[/red] {key}: {str(e)[:50]}")
            fail_count += 1

    console.print(f"[dim]  → {success_count} success, {fail_count} failed[/dim]")


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

    # Build secrets dynamically from config.yml (NO HARDCODING!)
    secrets = {
        # Infrastructure (generic, no app-specific logic)
        "CORE_EXTERNAL_IP": env["CORE_EXTERNAL_IP"],
        "CORE_INTERNAL_IP": env["CORE_INTERNAL_IP"],
        "DOCKER_REGISTRY": "docker.io",
        "DOCKER_ORG": env["DOCKER_ORG"],
        # Notifications
        "ALERT_EMAIL": env.get("ALERT_EMAIL", ""),  # Optional
        "FORGEJO_ORG": env["FORGEJO_ORG"],
        "REPO_SUPERDEPLOY": env.get("REPO_SUPERDEPLOY", "superdeploy"),
    }

    # Add optional app-specific URLs if defined in env
    if "PUBLIC_URL" in merged_env:
        secrets["PUBLIC_URL"] = merged_env["PUBLIC_URL"]
    if "SENTRY_DSN" in merged_env:
        secrets["SENTRY_DSN"] = merged_env["SENTRY_DSN"]

    # Add core service secrets dynamically (read from merged_env)
    # This supports ANY core service (postgres, rabbitmq, redis, memcached, etc.)
    core_service_patterns = {
        "postgres": {
            "host": "POSTGRES_HOST",
            "user": "POSTGRES_USER",
            "password": "POSTGRES_PASSWORD",
            "db": "POSTGRES_DB",
            "port": "POSTGRES_PORT",
        },
        "rabbitmq": {
            "host": "RABBITMQ_HOST",
            "user": "RABBITMQ_USER",
            "password": "RABBITMQ_PASSWORD",
            "port": "RABBITMQ_PORT",
        },
        "redis": {
            "host": "REDIS_HOST",
            "password": "REDIS_PASSWORD",
            "port": "REDIS_PORT",
        },
        "memcached": {"host": "MEMCACHED_HOST", "port": "MEMCACHED_PORT"},
    }

    for service, fields in core_service_patterns.items():
        for field_key, env_key in fields.items():
            if env_key in merged_env:
                secrets[env_key] = merged_env[env_key]

    # Add service-specific secrets dynamically (no hardcoding!)
    for key, value in merged_env.items():
        if key.endswith("_SECRET_KEY") or key == "PROXY_REGISTRY_API_KEY":
            secrets[key] = value

    success_count = 0
    fail_count = 0
    skip_count = 0

    for key, value in secrets.items():
        # Skip empty values (Forgejo returns 422 for empty secrets)
        if not value or value == "":
            console.print(f"  [dim]⊘[/dim] {key} (empty, skipped)")
            skip_count += 1
            continue

        try:
            response = requests.put(
                f"{forgejo_url}/api/v1/repos/{org}/{repo}/actions/secrets/{key}",
                headers={
                    "Authorization": f"token {forgejo_pat}",
                    "Content-Type": "application/json",
                },
                json={"data": value},
                timeout=3,  # Fast timeout - Forgejo should respond quickly
            )
            if response.status_code in [200, 201, 204]:
                console.print(f"  [green]✓[/green] {key}")
                success_count += 1
            else:
                console.print(f"  [yellow]⚠[/yellow] {key}: {response.status_code}")
                fail_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {key}: {str(e)[:50]}")
            fail_count += 1

    console.print(
        f"\n[green]✅ Forgejo secrets synced: {success_count} success, {fail_count} failed, {skip_count} skipped[/green]"
    )


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
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
      superdeploy sync -p myproject -e ../my-api/.env -e ../my-dashboard/.env

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

    # Load project-specific secrets from .passwords.yml (auto-generated by init)
    passwords_file = project_path / ".passwords.yml"
    project_secrets = {}

    if passwords_file.exists():
        import yaml

        with open(passwords_file) as f:
            passwords_data = yaml.safe_load(f)
            if passwords_data and "passwords" in passwords_data:
                project_secrets = passwords_data["passwords"]
                console.print(
                    f"[dim]✓ Loaded project passwords: {passwords_file}[/dim]"
                )

    # Also load secrets.env if exists (for custom secrets)
    secrets_file = project_path / "secrets.env"
    if secrets_file.exists():
        from dotenv import dotenv_values

        custom_secrets = dotenv_values(secrets_file)
        project_secrets.update(custom_secrets)
        console.print(f"[dim]✓ Loaded custom secrets: {secrets_file}[/dim]")

    # Merge all: infra → project passwords → custom secrets → additional
    env.update(project_secrets)
    env.update(additional_envs)

    # Auto-generate missing required secrets based on project name
    project_name = project
    if "POSTGRES_USER" not in env or not env["POSTGRES_USER"]:
        env["POSTGRES_USER"] = f"{project_name}_user"
    if "POSTGRES_DB" not in env or not env["POSTGRES_DB"]:
        env["POSTGRES_DB"] = f"{project_name}_db"
    if "RABBITMQ_USER" not in env or not env["RABBITMQ_USER"]:
        env["RABBITMQ_USER"] = f"{project_name}_user"

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

    # Try project.yml first (new format), fallback to config.yml (old format)
    config_file = project_path / "project.yml"
    if not config_file.exists():
        config_file = project_path / "config.yml"
    
    if not config_file.exists():
        console.print(f"[red]✗[/red] Project config not found: {project_path}/project.yml")
        console.print(f"[yellow]Create project.yml for project '{project}'[/yellow]")
        raise SystemExit(1)

    with open(config_file) as f:
        project_config = yaml.safe_load(f)

    # GitHub repos from project config
    repos = project_config.get("github", {}).get("repositories", {})

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
                # Update .env file (use absolute path)
                import pathlib

                env_file_path = pathlib.Path(__file__).parent.parent.parent / ".env"

                if not env_file_path.exists():
                    console.print(f"[red]✗[/red] .env not found at {env_file_path}")
                else:
                    with open(env_file_path, "r") as f:
                        lines = f.readlines()

                    with open(env_file_path, "w") as f:
                        for line in lines:
                            if line.startswith("FORGEJO_PAT="):
                                f.write(f"FORGEJO_PAT={forgejo_pat}\n")
                            else:
                                f.write(line)

                    console.print(
                        f"[green]✅ Forgejo PAT saved to {env_file_path}[/green]"
                    )

                # Update env dict so it's used in GitHub secrets sync
                env["FORGEJO_PAT"] = forgejo_pat

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

    # Step 3: Sync to GitHub (outside progress bar for better visibility)
    console.print(
        "\n[bold cyan]📤 Syncing secrets to GitHub repositories...[/bold cyan]"
    )

    for app_name, repo in repos.items():
        console.print(f"\n[bold cyan]━━━ {app_name.upper()} ({repo}) ━━━[/bold cyan]")

        # Repository secrets (infrastructure/build related)
        repo_secrets = {
            "AGE_PUBLIC_KEY": age_public_key,
            "FORGEJO_BASE_URL": f"http://{env['CORE_EXTERNAL_IP']}:3001",
            "FORGEJO_ORG": env["FORGEJO_ORG"],
            "FORGEJO_REPO": env.get("REPO_SUPERDEPLOY", "superdeploy"),
            "FORGEJO_PAT": forgejo_pat,
            "PROJECT_NAME": project,  # ✅ Generic project name
            "DOCKER_USERNAME": env["DOCKER_USERNAME"],
            "DOCKER_TOKEN": env["DOCKER_TOKEN"],
            "CORE_EXTERNAL_IP": env[
                "CORE_EXTERNAL_IP"
            ],  # For API_BASE_URL construction
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

            # Base secrets (common for all services) - FULLY DYNAMIC!
            env_secrets = {
                "LOG_LEVEL": "DEBUG" if env_name == "staging" else "INFO",
                "SMTP_USERNAME": env.get("SMTP_USERNAME", ""),
                "SMTP_PASSWORD": env.get("SMTP_PASSWORD", ""),
            }

            # Add optional app-specific URLs if defined
            if "PUBLIC_URL" in merged_env:
                env_secrets["PUBLIC_URL"] = merged_env["PUBLIC_URL"]
            if "API_BASE_URL" in merged_env:
                env_secrets["API_BASE_URL"] = merged_env["API_BASE_URL"]
            if "SENTRY_DSN" in merged_env:
                env_secrets["SENTRY_DSN"] = merged_env["SENTRY_DSN"]

            # Add core service secrets dynamically (NO HARDCODING!)
            for service, fields in core_service_patterns.items():
                for field_key, env_key in fields.items():
                    if env_key in merged_env:
                        env_secrets[env_key] = merged_env[env_key]

            # Add service-specific secrets (generic pattern, no hardcoding!)
            service_upper = app_name.upper()
            service_secret_key = f"{service_upper}_SECRET_KEY"
            if service_secret_key in merged_env:
                env_secrets[service_secret_key] = merged_env[service_secret_key]

            # Add APP_TITLE for branding
            env_secrets["APP_TITLE"] = f"{project.title()} {app_name.title()}"

            # Add PROXY_REGISTRY_API_KEY if exists
            if "PROXY_REGISTRY_API_KEY" in merged_env:
                env_secrets["PROXY_REGISTRY_API_KEY"] = merged_env[
                    "PROXY_REGISTRY_API_KEY"
                ]

            set_github_env_secrets(repo, env_name, env_secrets)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Sync Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("\n[white]Next steps:[/white]")
    console.print("  1. Push to GitHub: [cyan]git push origin production[/cyan]")
    console.print("  2. Deployment will auto-trigger!")
    console.print("\n[dim]All secrets have been configured automatically.[/dim]")
