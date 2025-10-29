import os

"""SuperDeploy CLI - Logs command"""

import click
import subprocess
from rich.console import Console
from cli.utils import load_env, validate_env_vars

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-f", "--follow", is_flag=True, help="Follow logs (tail -f)")
@click.option("-n", "--lines", default=100, help="Number of lines")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def logs(project, app, follow, lines, environment):
    """
    View application logs

    \b
    Examples:
      superdeploy logs -a api              # Last 100 lines
      superdeploy logs -a api -f           # Follow logs
      superdeploy logs -a api -n 500       # Last 500 lines
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    
    console.print(f"[cyan]📋 Fetching logs for [bold]{project}/{app}[/bold]...[/cyan]")
    
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
        
        # Get VM IP from Terraform outputs or inventory
        inventory_path = projects_dir / project / "inventory.ini"
        if not inventory_path.exists():
            console.print(f"[red]❌ Inventory not found. Run: superdeploy up -p {project}[/red]")
            return
        
        # Parse inventory to get VM IP
        inventory_content = inventory_path.read_text()
        import re
        pattern = rf"{project}-{vm_role}-\d+\s+ansible_host=(\S+)"
        match = re.search(pattern, inventory_content)
        
        if not match:
            console.print(f"[red]❌ VM not found in inventory for role: {vm_role}[/red]")
            return
        
        ssh_host = match.group(1)
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return
    
    # SSH config
    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"

    follow_flag = "-f" if follow else ""
    # Container naming: {project}-{app}
    docker_cmd = f"docker logs {follow_flag} --tail {lines} {project}-{app} 2>&1"

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
        # Stream logs to terminal
        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        console.print(f"[green]✅ Streaming logs from {app}...[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        for line in process.stdout:
            print(line, end="")

        process.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Stopped[/yellow]")
        process.terminate()
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to fetch logs: {e}[/red]")
        raise SystemExit(1)
