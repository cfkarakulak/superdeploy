import os

"""SuperDeploy CLI - Run command"""

import click
import subprocess
from rich.console import Console
from cli.utils import load_env, validate_env_vars

console = Console()


@click.command(name="run")
@click.option("--project", "-p", required=True, help="Project name")
@click.argument("app")
@click.argument("command")
def run(project, app, command):
    """
    Run one-off command in app container

    \b
    Examples:
      superdeploy run api "python manage.py migrate"
      superdeploy run api "bash"
      superdeploy run dashboard "npm install"
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    
    console.print(f"[cyan]⚡ Running command in [bold]{app}[/bold]:[/cyan]")
    console.print(f"[dim]$ {command}[/dim]\n")
    
    # Load config to find VM
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        
        if app not in apps:
            console.print(f"[red]❌ App '{app}' not found in project config[/red]")
            return
        
        vm_role = apps[app].get("vm", "core")
        
        # Get VM IP from .env
        from cli.utils import load_env
        env = load_env(project=project)
        
        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            console.print(f"[red]❌ VM IP not found in .env: {ip_key}[/red]")
            console.print(f"[dim]Run: superdeploy up -p {project}[/dim]")
            return
        
        ssh_host = env[ip_key]
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return
    
    # SSH config
    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"

    # Use -i (not -it) for non-interactive commands to avoid TTY errors
    docker_cmd = f"docker exec -i {project}-{app} {command}"

    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        f"{ssh_user}@{ssh_host}",
        docker_cmd,
    ]

    try:
        result = subprocess.run(ssh_cmd, check=True)

        if result.returncode == 0:
            console.print("\n[green]✅ Command executed successfully![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Command failed with exit code {e.returncode}[/red]")
        raise SystemExit(e.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Interrupted[/yellow]")
        raise SystemExit(130)
