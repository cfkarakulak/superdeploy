"""SuperDeploy CLI - Sync Infrastructure Secrets"""

import os
import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from cli.utils import load_env, ssh_command, validate_env_vars, get_project_root
# parse_project_config removed - use ConfigLoader instead if needed

console = Console()


def get_age_public_key(env, forgejo_host):
    """Fetch AGE public key from runner VM"""
    try:
        key_file = ssh_command(
            host=forgejo_host,
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


def create_forgejo_pat(env, forgejo_host):
    """Create Forgejo Personal Access Token"""
    console.print("[dim]Creating Forgejo PAT...[/dim]")

    import requests
    import time

    forgejo_url = f"http://{forgejo_host}:3001"
    token_name = f"github-actions-{int(time.time())}"

    try:
        # Comprehensive scopes for workflow dispatch and repository access
        scopes = [
            "write:activitypub",
            "write:admin",
            "write:issue",
            "write:misc",
            "write:notification",
            "write:organization",
            "write:package",
            "write:repository",
            "write:user",
        ]
        
        response = requests.post(
            f"{forgejo_url}/api/v1/users/{env['FORGEJO_ADMIN_USER']}/tokens",
            auth=(env["FORGEJO_ADMIN_USER"], env["FORGEJO_ADMIN_PASSWORD"]),
            json={"name": token_name, "scopes": scopes},
            timeout=10,
        )

        if response.status_code == 201:
            token = response.json()["sha1"]
            console.print(f"[green]✓[/green] Forgejo PAT created (prefix: {token[:10]}...)")
            return token
        else:
            console.print(f"[red]✗[/red] Failed (HTTP {response.status_code}): {response.text}")
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
    env = load_env(project)

    # Validate required vars (from infrastructure)
    required = [
        "SSH_KEY_PATH",
        "FORGEJO_ADMIN_USER",
        "FORGEJO_ADMIN_PASSWORD",
        "DOCKER_USERNAME",
        "DOCKER_TOKEN",
    ]

    if not validate_env_vars(env, required):
        raise SystemExit(1)

    # Get GitHub org and repos from project config
    project_root = get_project_root()

    # Load project configuration using ConfigLoader
    try:
        from cli.core.config_loader import ConfigLoader
        
        projects_dir = project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        project_config_obj = config_loader.load_project(project)
        
        github_org = project_config_obj.raw_config.get("github", {}).get(
            "organization", f"{project}io"
        )
        # Get service names from apps configuration
        services = list(project_config_obj.get_apps().keys())
        if not services:
            services = ["api", "dashboard", "services"]  # Default fallback
    except (FileNotFoundError, ValueError):
        # If project config doesn't exist, use defaults
        github_org = env.get("GITHUB_ORG", f"{project}io")
        services = ["api", "dashboard", "services"]

    console.print("\n[cyan]📦 Target repositories:[/cyan]")
    for service in services:
        console.print(f"  • {github_org}/{service}")
    
    # Find which VM runs Forgejo by checking project config
    vms_config = project_config_obj.get_vms()
    forgejo_vm_role = None
    forgejo_vm_index = 0
    
    for vm_role, vm_def in vms_config.items():
        services_list = vm_def.get("services", [])
        if "forgejo" in services_list:
            forgejo_vm_role = vm_role
            forgejo_vm_index = 0  # Use first instance of this VM role
            break
    
    if not forgejo_vm_role:
        console.print("[red]❌ Forgejo not found in any VM configuration![/red]")
        console.print("[dim]Add 'forgejo' to a VM's services list in project.yml[/dim]")
        raise SystemExit(1)
    
    # Build the env var name for this VM (e.g., CORE_0_EXTERNAL_IP)
    forgejo_ip_var = f"{forgejo_vm_role.upper()}_{forgejo_vm_index}_EXTERNAL_IP"
    
    if forgejo_ip_var not in env:
        console.print(f"[red]❌ {forgejo_ip_var} not found in environment![/red]")
        console.print(f"[dim]Run 'superdeploy up -p {project}' to provision VMs[/dim]")
        raise SystemExit(1)
    
    forgejo_host = env[forgejo_ip_var]
    console.print(f"[dim]Using Forgejo host: {forgejo_host} (from {forgejo_vm_role}-{forgejo_vm_index})[/dim]")

    # Step 1: Fetch AGE public key
    console.print("\n[cyan]1️⃣ Fetching AGE public key from runner...[/cyan]")
    age_public_key = get_age_public_key(env, forgejo_host)
    if not age_public_key:
        console.print("[red]❌ Failed to get AGE key[/red]")
        raise SystemExit(1)
    console.print(f"[green]✓[/green] AGE key: {age_public_key[:20]}...")

    # Step 2: Create Forgejo PAT
    console.print("\n[cyan]2️⃣ Creating Forgejo PAT...[/cyan]")
    forgejo_pat = create_forgejo_pat(env, forgejo_host)
    if not forgejo_pat:
        console.print("[red]❌ Failed to create Forgejo PAT[/red]")
        raise SystemExit(1)
    console.print("[green]✓[/green] PAT created")
    
    # Update .env file with new PAT
    env_file_path = project_root / "projects" / project / ".env"
    if env_file_path.exists():
        with open(env_file_path, "r") as f:
            lines = f.readlines()
        
        # Update FORGEJO_PAT line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("FORGEJO_PAT="):
                lines[i] = f"FORGEJO_PAT={forgejo_pat}  # Generated by sync:infra\n"
                updated = True
                break
        
        # If not found, append it
        if not updated:
            lines.append(f"\n# Forgejo PAT (Auto-generated)\n")
            lines.append(f"FORGEJO_PAT={forgejo_pat}  # Generated by sync:infra\n")
        
        with open(env_file_path, "w") as f:
            f.writelines(lines)
        
        console.print(f"[green]✓[/green] Updated .env with new PAT")

    # Step 3: Sync to GitHub
    console.print("\n[cyan]3️⃣ Syncing to GitHub repositories...[/cyan]")

    infra_secrets = {
        "FORGEJO_BASE_URL": f"http://{forgejo_host}:3001",
        "FORGEJO_URL": f"http://{forgejo_host}:3001",
        "FORGEJO_PAT": forgejo_pat,
        "AGE_PUBLIC_KEY": age_public_key,
        "DOCKER_USERNAME": env["DOCKER_USERNAME"],
        "DOCKER_TOKEN": env["DOCKER_TOKEN"],
        "PROJECT": project,
        "FORGEJO_ORG": env.get("FORGEJO_ORG"),
        "FORGEJO_REPO": env.get("FORGEJO_REPO", "superdeploy"),
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
