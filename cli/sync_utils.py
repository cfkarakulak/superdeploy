"""SuperDeploy CLI - Sync utility functions"""

import os
import subprocess
from rich.console import Console

console = Console()


def get_core_service_patterns(project_name, env):
    """
    Build service patterns dynamically from addon metadata.

    Args:
        project_name (str): Project name
        env (dict): Environment variables

    Returns:
        dict: Dictionary mapping addon names to their environment variable lists
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
        project_config = config_loader.load_project(project_name)

        # Load addons
        addons = addon_loader.load_addons_for_project(project_config.raw_config)

        # Build patterns dynamically
        patterns = {}
        for addon_name, addon in addons.items():
            env_var_names = addon.get_env_var_names()
            if env_var_names:
                patterns[addon_name] = env_var_names

        return patterns
    except Exception as e:
        # Fallback to empty dict if addon loading fails
        console.print(f"[dim]Could not load addon patterns: {e}[/dim]")
        return {}


def get_age_public_key(project_name, env):
    """
    Fetch AGE public key from runner VM (dynamic - finds infrastructure VM)

    Args:
        project_name (str): Project name
        env (dict): Environment variables with VM IPs and SSH config

    Returns:
        str: AGE public key or None if failed
    """
    from cli.utils import ssh_command, get_ssh_connection_info

    try:
        # Get infrastructure VM connection info
        ssh_info = get_ssh_connection_info(project_name)

        # Read entire key file, then parse locally
        key_file = ssh_command(
            host=ssh_info["host"],
            user=ssh_info["user"],
            key_path=os.path.expanduser(ssh_info["key_path"]),
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


def create_forgejo_pat(project_name, env):
    """
    Create Forgejo Personal Access Token (dynamic - finds infrastructure VM)

    Args:
        project_name (str): Project name
        env (dict): Environment variables with Forgejo config

    Returns:
        str: Forgejo PAT or None if failed
    """
    import requests
    import time
    from cli.utils import get_infrastructure_vm_ip

    console.print("[dim]Creating Forgejo PAT...[/dim]")

    infra_ip = get_infrastructure_vm_ip(project_name)
    if not infra_ip:
        console.print("[red]❌ Infrastructure VM IP not found[/red]")
        return None

    forgejo_url = f"http://{infra_ip}:3001"
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
            timeout=10,
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


def sync_secrets_to_forgejo(project_name, env, forgejo_pat, project_secrets=None):
    """
    Sync secrets to Forgejo repository (dynamic - finds infrastructure VM)

    Args:
        project_name (str): Project name
        env (dict): Environment variables
        forgejo_pat (str): Forgejo Personal Access Token
        project_secrets (dict): Optional project-specific secrets to merge

    Returns:
        tuple: (success_count, fail_count, skip_count)
    """
    import requests
    from cli.utils import get_infrastructure_vm_ip

    infra_ip = get_infrastructure_vm_ip(project_name)
    if not infra_ip:
        console.print("[red]❌ Infrastructure VM IP not found[/red]")
        return (0, 0, 0)

    forgejo_url = f"http://{infra_ip}:3001"
    org = env["FORGEJO_ORG"]
    repo = env["REPO_SUPERDEPLOY"]

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
            return (0, 0, 0)
    except Exception as e:
        console.print(f"[yellow]⚠️  Forgejo not accessible: {e}[/yellow]")
        return (0, 0, 0)

    # Merge project-specific secrets if provided
    merged_env = {**env}
    if project_secrets:
        merged_env.update(project_secrets)

    # Build secrets dynamically from config
    secrets = {
        # Infrastructure (dynamic - all VM IPs)
        "DOCKER_REGISTRY": "docker.io",
        "DOCKER_ORG": env["DOCKER_ORG"],
        "FORGEJO_ORG": env["FORGEJO_ORG"],
        "REPO_SUPERDEPLOY": env.get("REPO_SUPERDEPLOY", "superdeploy"),
    }

    # Add all VM IPs dynamically
    for key, value in merged_env.items():
        if key.endswith("_EXTERNAL_IP") or key.endswith("_INTERNAL_IP"):
            secrets[key] = value

    # Add optional fields
    optional_fields = ["ALERT_EMAIL", "PUBLIC_URL"]
    for field in optional_fields:
        if field in merged_env:
            secrets[field] = merged_env[field]

    # Add core service secrets dynamically from addon metadata
    core_service_patterns = get_core_service_patterns(project_name, merged_env)

    for service, fields in core_service_patterns.items():
        for field in fields:
            if field in merged_env:
                secrets[field] = merged_env[field]

    # Add service-specific secrets
    for key, value in merged_env.items():
        if key.endswith("_SECRET_KEY") or key == "PROXY_REGISTRY_API_KEY":
            secrets[key] = value

    success_count = 0
    fail_count = 0
    skip_count = 0

    console.print(f"[cyan]Syncing to Forgejo ({org}/{repo})...[/cyan]")

    for key, value in secrets.items():
        # Skip empty values
        if not value or value == "":
            console.print(
                f"  [color(208)]⊘[/color(208)] [dim]{key} (empty, skipped)[/dim]"
            )
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
                timeout=3,
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

    return (success_count, fail_count, skip_count)


def sync_secrets_to_github(repo, secrets):
    """
    Sync secrets to GitHub repository

    Args:
        repo (str): GitHub repository (owner/repo)
        secrets (dict): Secrets to sync

    Returns:
        tuple: (success_count, fail_count)
    """
    console.print(f"[dim]Setting repository secrets for {repo}...[/dim]")

    success_count = 0
    fail_count = 0

    for key, value in secrets.items():
        # Skip empty values
        if not value or value == "":
            console.print(
                f"  [color(208)]⊘[/color(208)] [dim]{key} (empty, skipped)[/dim]"
            )
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

    return (success_count, fail_count)


def create_github_environment(repo, env_name):
    """
    Create GitHub environment if it doesn't exist

    Args:
        repo (str): GitHub repository (owner/repo)
        env_name (str): Environment name (production, staging)

    Returns:
        bool: True if successful
    """
    try:
        # Check if environment exists
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/environments/{env_name}"],
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            # Create environment
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


def sync_github_env_secrets(repo, env_name, secrets):
    """
    Sync secrets to GitHub environment

    Args:
        repo (str): GitHub repository (owner/repo)
        env_name (str): Environment name
        secrets (dict): Secrets to sync

    Returns:
        tuple: (success_count, fail_count)
    """
    console.print(f"[dim]Setting environment secrets for {repo} ({env_name})...[/dim]")

    success_count = 0
    fail_count = 0

    for key, value in secrets.items():
        # Skip empty values
        if not value or value == "":
            console.print(
                f"  [color(208)]⊘[/color(208)] [dim]{key} (empty, skipped)[/dim]"
            )
            continue

        try:
            result = subprocess.run(
                ["gh", "secret", "set", key, "-b", value, "-e", env_name, "-R", repo],
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
            console.print(f"  [red]✗[/red] {key}: {error_msg[:50]}")
            fail_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {key}: {str(e)[:50]}")
            fail_count += 1

    return (success_count, fail_count)
