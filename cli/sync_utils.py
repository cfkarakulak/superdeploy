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
