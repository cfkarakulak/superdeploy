"""SuperDeploy CLI - Restart command"""

import click
import subprocess
from rich.console import Console
from pathlib import Path

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
def restart(project, app):
    """
    Restart an application container
    
    \b
    Example:
      superdeploy restart -p cheapa -a api
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    import re
    
    console.print(f"\n[cyan]🔄 Restarting {project}/{app}...[/cyan]\n")
    
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    # Load config to find VM
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        
        if app not in apps:
            console.print(f"[red]❌ App '{app}' not found in project config[/red]")
            return
        
        vm_role = apps[app].get("vm", "core")
        
        # Get VM IP from inventory
        inventory_path = project_root / "shared" / "ansible" / "inventories" / f"{project}.ini"
        if not inventory_path.exists():
            console.print(f"[red]❌ Inventory not found. Run: superdeploy up -p {project}[/red]")
            return
        
        inventory_content = inventory_path.read_text()
        pattern = rf"{project}-{vm_role}-\d+\s+ansible_host=(\S+)"
        match = re.search(pattern, inventory_content)
        
        if not match:
            console.print(f"[red]❌ VM not found in inventory for role: {vm_role}[/red]")
            return
        
        ssh_host = match.group(1)
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return
    
    # SSH and restart container
    ssh_key = Path.home() / ".ssh" / "superdeploy_deploy"
    container_name = f"{project}-{app}"
    
    cmd = [
        "ssh", "-i", str(ssh_key),
        "-o", "StrictHostKeyChecking=no",
        f"superdeploy@{ssh_host}",
        f"docker restart {container_name}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        console.print(f"[green]✅ {app} restarted successfully![/green]\n")
        
        # Show status
        status_cmd = [
            "ssh", "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"superdeploy@{ssh_host}",
            f"docker ps --filter name={container_name} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'"
        ]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)
        console.print("[cyan]Status:[/cyan]")
        console.print(status_result.stdout)
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Restart failed: {e.stderr}[/red]")
