"""SuperDeploy CLI - Restart command"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from cli.logger import DeployLogger

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def restart(project, app, verbose):
    """
    Restart an application container
    
    \b
    Example:
      superdeploy restart -p cheapa -a api
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    import re
    
    if not verbose:
        console.print(
            Panel.fit(
                f"[bold cyan]🔄 Restart Application[/bold cyan]\n\n"
                f"[white]Project: {project}[/white]\n"
                f"[white]App: {app}[/white]",
                border_style="cyan",
            )
        )
    
    logger = DeployLogger(project, f"restart-{app}", verbose=verbose)
    
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    # Load config to find VM
    logger.step("Loading project configuration")
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        logger.success("Configuration loaded")
        
        if app not in apps:
            logger.log_error(f"App '{app}' not found in project config")
            raise SystemExit(1)
        
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
            logger.log_error(f"VM not found in inventory for role: {vm_role}")
            raise SystemExit(1)
        
        ssh_host = match.group(1)
        logger.log(f"Found VM: {ssh_host}")
        
    except Exception as e:
        logger.log_error(f"Error: {e}")
        raise SystemExit(1)
    
    # SSH and restart container
    logger.step(f"Restarting {app} container")
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
        logger.success(f"{app} restarted successfully")
        
        # Show status
        logger.log("Checking container status")
        status_cmd = [
            "ssh", "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"superdeploy@{ssh_host}",
            f"docker ps --filter name={container_name} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'"
        ]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)
        
        if not verbose:
            console.print("\n[cyan]Status:[/cyan]")
            console.print(status_result.stdout)
            console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
        
    except subprocess.CalledProcessError as e:
        logger.log_error(f"Restart failed: {e.stderr}")
        raise SystemExit(1)
