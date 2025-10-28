import os

"""SuperDeploy CLI - Sync command (AGE key + GitHub secrets automation)"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.utils import load_env, ssh_command, validate_env_vars

console = Console()


def build_service_patterns_from_addons(project, env):
    """
    Build service patterns dynamically from addon metadata.
    
    Args:
        project (str): Project name
        env (dict): Environment variables
        
    Returns:
        dict: Dictionary mapping addon names to their environment variable structure
    """
    from cli.core.addon_loader import AddonLoader
    from cli.utils import get_project_root
    
    try:
        project_root = get_project_root()
        addons_dir = project_root / "addons"
        addon_loader = AddonLoader(addons_dir)
        
        # Load project config to get enabled addons
        from cli.core.config_loader import ConfigLoader
        projects_dir = project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        
        # Load addons
        addons = addon_loader.load_addons_for_project(project_config.raw_config)
        
        # Build patterns from addon env.yml
        patterns = {}
        for addon_name, addon in addons.items():
            addon_structure = addon.get_env_var_structure()
            if addon_structure:
                patterns[addon_name] = addon_structure
        
        return patterns
    except Exception as e:
        # Fallback to empty dict if addon loading fails
        console.print(f"[dim]Could not load addon patterns: {e}[/dim]")
        return {}


def get_age_public_key(env, forgejo_host):
    """Fetch AGE public key from runner VM"""
    try:
        # Read entire key file, then parse locally
        key_file = ssh_command(
            host=forgejo_host,
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


def create_forgejo_pat(env, forgejo_host):
    """Create Forgejo Personal Access Token"""
    console.print("[dim]Creating Forgejo PAT...[/dim]")

    import requests
    import time

    forgejo_url = f"http://{forgejo_host}:3001"
    token_name = f"github-actions-{int(time.time())}"

    try:
        response = requests.post(
            f"{forgejo_url}/api/v1/users/{env['FORGEJO_ADMIN_USER']}/tokens",
            auth=(env["FORGEJO_ADMIN_USER"], env["FORGEJO_ADMIN_PASSWORD"]),
            json={
                "name": token_name,
                "scopes": [
                    "write:activitypub",
                    "write:admin",
                    "write:issue",
                    "write:misc",
                    "write:notification",
                    "write:organization",
                    "write:package",
                    "write:repository",
                    "write:user",
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


def sync_forgejo_secrets(env, forgejo_pat, forgejo_host, project_env=None, age_secret_key=None, project_name=None):
    """Sync all secrets to Forgejo repository"""
    import requests

    forgejo_url = f"http://{forgejo_host}:3001"
    org = env["FORGEJO_ORG"]  # No fallback - MUST exist
    repo = env["REPO_SUPERDEPLOY"]  # No fallback - MUST exist

    # Test connection first
    try:
        test_response = requests.get(
            f"{forgejo_url}/api/v1/user",
            headers={"Authorization": f"token {forgejo_pat}"},
            timeout=5,
        )
        if test_response.status_code == 401:
            console.print(
                f"[red]✗[/red] Forgejo PAT is invalid or expired (HTTP 401)"
            )
            console.print(f"[dim]Response: {test_response.text}[/dim]")
            console.print(f"[yellow]Run 'superdeploy sync -p {env.get('PROJECT', 'PROJECT')}' to regenerate PAT[/yellow]")
            return
        elif test_response.status_code != 200:
            console.print(
                f"[yellow]⚠️  Forgejo API returned HTTP {test_response.status_code}[/yellow]"
            )
            console.print(f"[dim]Response: {test_response.text}[/dim]")
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
        "FORGEJO_HOST": forgejo_host,
        "FORGEJO_PAT": forgejo_pat,  # Add PAT so Forgejo can use it
        "DOCKER_REGISTRY": "docker.io",
        "DOCKER_ORG": env["DOCKER_ORG"],
        # Notifications
        "ALERT_EMAIL": env.get("ALERT_EMAIL", ""),  # Optional
        "FORGEJO_ORG": env["FORGEJO_ORG"],
        "REPO_SUPERDEPLOY": env.get("REPO_SUPERDEPLOY", "superdeploy"),
    }
    
    # Add AGE secret key if provided
    if age_secret_key:
        secrets["AGE_SECRET_KEY"] = age_secret_key

    # Add optional app-specific URLs if defined in env
    if "PUBLIC_URL" in merged_env:
        secrets["PUBLIC_URL"] = merged_env["PUBLIC_URL"]
    if "SENTRY_DSN" in merged_env:
        secrets["SENTRY_DSN"] = merged_env["SENTRY_DSN"]

    # Add core service secrets dynamically from addon metadata
    if not project_name:
        # Fallback: try to get from repo name
        project_name = repo.split("/")[-1] if "/" in repo else repo
    core_service_patterns = build_service_patterns_from_addons(project_name, merged_env)
    
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
    from cli.utils import validate_project, get_project_path, get_project_root
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
    env = load_env(project)

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

    # All secrets are now in .env (already loaded via load_env)
    project_secrets = {}

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

    # Find which VM runs Forgejo by checking project config
    from cli.core.config_loader import ConfigLoader
    
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    config_loader = ConfigLoader(projects_dir)
    
    try:
        project_config_obj = config_loader.load_project(project)
    except FileNotFoundError:
        console.print(f"[red]✗[/red] Project config not found")
        raise SystemExit(1)
    
    vms_config = project_config_obj.get_vms()
    forgejo_vm_role = None
    forgejo_vm_index = 0
    
    for vm_role, vm_def in vms_config.items():
        services_list = vm_def.get("services", [])
        if "forgejo" in services_list:
            forgejo_vm_role = vm_role
            forgejo_vm_index = 0
            break
    
    if not forgejo_vm_role:
        console.print("[red]❌ Forgejo not found in any VM configuration![/red]")
        raise SystemExit(1)
    
    # Build the env var name for this VM (e.g., CORE_0_EXTERNAL_IP)
    forgejo_ip_var = f"{forgejo_vm_role.upper()}_{forgejo_vm_index}_EXTERNAL_IP"
    
    if forgejo_ip_var not in env:
        console.print(f"[red]❌ {forgejo_ip_var} not found in environment![/red]")
        console.print(f"[dim]Run 'superdeploy up -p {project}' to provision VMs[/dim]")
        raise SystemExit(1)
    
    forgejo_host = env[forgejo_ip_var]
    console.print(f"[dim]Using Forgejo host: {forgejo_host} (from {forgejo_vm_role}-{forgejo_vm_index})[/dim]")
    
    # Add to env for backward compatibility
    env["FORGEJO_HOST"] = forgejo_host

    # Validate required vars
    required = ["SSH_KEY_PATH"]
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
    # Load project config using ConfigLoader
    from cli.core.config_loader import ConfigLoader
    
    try:
        project_root = get_project_root()
        projects_dir = project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        project_config_obj = config_loader.load_project(project)
        project_config = project_config_obj.raw_config
    except FileNotFoundError:
        console.print(f"[red]✗[/red] Project config not found: {project_path}/project.yml")
        console.print(f"[yellow]Create project.yml for project '{project}'[/yellow]")
        raise SystemExit(1)

    # GitHub repos from project config
    # Build repos dict from apps config: {app_name: "org/app_name"}
    github_org = project_config.get("github", {}).get("organization", f"{project}io")
    apps = project_config.get("apps", {})
    repos = {app_name: f"{github_org}/{app_name}" for app_name in apps.keys()}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Fetch AGE public key
        task1 = progress.add_task("[cyan]Fetching AGE public key from VM...", total=1)
        age_public_key = get_age_public_key(env, forgejo_host)

        if not age_public_key:
            console.print("[red]❌ Failed to fetch AGE public key![/red]")
            raise SystemExit(1)

        progress.advance(task1)
        console.print(f"[green]✅ AGE Public Key: {age_public_key[:30]}...[/green]")

        # Step 2: Create Forgejo PAT (if not exists or invalid)
        task2 = progress.add_task("[cyan]Creating Forgejo PAT...", total=1)

        forgejo_pat = env.get("FORGEJO_PAT")
        
        # Test existing PAT if present
        pat_valid = False
        if forgejo_pat and forgejo_pat != "auto-generated" and not skip_forgejo:
            try:
                import requests
                test_response = requests.get(
                    f"http://{env['CORE_EXTERNAL_IP']}:3001/api/v1/user",
                    headers={"Authorization": f"token {forgejo_pat}"},
                    timeout=5,
                )
                pat_valid = (test_response.status_code == 200)
                if not pat_valid:
                    console.print(f"[dim]Existing PAT invalid (HTTP {test_response.status_code}), creating new one...[/dim]")
            except:
                pass
        
        if not forgejo_pat or forgejo_pat == "auto-generated" or skip_forgejo or not pat_valid:
            forgejo_pat = create_forgejo_pat(env, forgejo_host)

            if forgejo_pat:
                # Update .env file in project directory
                from cli.utils import get_project_root
                
                project_root = get_project_root()
                env_file_path = project_root / "projects" / project / ".env"

                if not env_file_path.exists():
                    console.print(f"[yellow]⚠[/yellow] .env not found at {env_file_path}, skipping save")
                else:
                    with open(env_file_path, "r") as f:
                        lines = f.readlines()

                    updated = False
                    with open(env_file_path, "w") as f:
                        for line in lines:
                            if line.startswith("FORGEJO_PAT="):
                                f.write(f"FORGEJO_PAT={forgejo_pat}\n")
                                updated = True
                            else:
                                f.write(line)
                        
                        # If FORGEJO_PAT line didn't exist, append it
                        if not updated:
                            f.write(f"\nFORGEJO_PAT={forgejo_pat}\n")

                    console.print(
                        f"[green]✅ Forgejo PAT saved to {env_file_path}[/green]"
                    )

                # Update env dict so it's used in GitHub secrets sync
                env["FORGEJO_PAT"] = forgejo_pat

        progress.advance(task2)

        # Step 2.5: Get AGE secret key
        age_secret_key = None
        try:
            age_key_file = ssh_command(
                host=forgejo_host,
                user=env.get("SSH_USER", "superdeploy"),
                key_path=os.path.expanduser(env["SSH_KEY_PATH"]),
                cmd="cat /opt/forgejo-runner/.age/key.txt",
            )
            # Extract secret key line (format: "AGE-SECRET-KEY-...")
            for line in age_key_file.split("\n"):
                if line.startswith("AGE-SECRET-KEY-"):
                    age_secret_key = line.strip()
                    break
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not fetch AGE secret key: {e}[/yellow]")
        
        # Step 2.6: Sync secrets to Forgejo repository
        if forgejo_pat:
            console.print(
                "\n[bold cyan]📝 Syncing secrets to Forgejo repository...[/bold cyan]"
            )
            sync_forgejo_secrets(env, forgejo_pat, forgejo_host, project_secrets, age_secret_key, project)

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
            "FORGEJO_BASE_URL": f"http://{forgejo_host}:3001",
            "FORGEJO_ORG": env["FORGEJO_ORG"],
            "FORGEJO_REPO": env.get("FORGEJO_REPO", "superdeploy"),
            "FORGEJO_PAT": forgejo_pat,
            "PROJECT_NAME": project,  # ✅ Generic project name
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

            # Add core service secrets dynamically from addon metadata
            core_service_patterns = build_service_patterns_from_addons(project, merged_env)
            
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
