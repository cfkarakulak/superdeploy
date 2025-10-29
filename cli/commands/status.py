"""SuperDeploy CLI - Status command"""

import os
import click
import re
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.utils import get_project_root, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
def status(project):
    """
    Show infrastructure and application status
    
    Displays:
    - VM status per role
    - Container status per VM
    - Application health
    """
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    # Load project config
    from cli.core.config_loader import ConfigLoader
    
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        config = project_config.raw_config
    except FileNotFoundError:
        console.print(f"[red]❌ Project '{project}' not found![/red]")
        return
    except ValueError as e:
        console.print(f"[red]❌ Error loading config: {e}[/red]")
        return
    
    console.print(f"[cyan]📊 Fetching status for {project}...[/cyan]\n")
    
    # Get inventory
    inventory_path = projects_dir / project / "inventory.ini"
    if not inventory_path.exists():
        console.print(f"[yellow]⚠️  No inventory found. Run: superdeploy up -p {project}[/yellow]")
        return
    
    # Parse inventory to get all VMs
    inventory_content = inventory_path.read_text()
    vm_pattern = r"(\S+)\s+ansible_host=(\S+)"
    vms = {}
    
    for match in re.finditer(vm_pattern, inventory_content):
        vm_name = match.group(1)
        vm_ip = match.group(2)
        # Extract role from vm_name (e.g., cheapa-api-0 -> api)
        role_match = re.match(rf"{project}-(\w+)-\d+", vm_name)
        if role_match:
            role = role_match.group(1)
            vms[role] = {"name": vm_name, "ip": vm_ip}
    
    if not vms:
        console.print("[yellow]⚠️  No VMs found in inventory[/yellow]")
        return
    
    # Get apps and their VM assignments
    apps = config.get("apps", {})
    
    # Create table
    table = Table(title=f"{project} - Infrastructure Status")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"
    
    # Check each VM and its containers
    for role, vm_info in vms.items():
        vm_ip = vm_info["ip"]
        vm_name = vm_info["name"]
        
        # Check VM uptime
        try:
            uptime_cmd = "uptime -p"
            uptime = ssh_command(host=vm_ip, user=ssh_user, key_path=ssh_key, cmd=uptime_cmd)
            uptime = uptime.strip().replace("up ", "")
            table.add_row(f"{role.upper()} VM", "✅ Running", f"{vm_ip} ({uptime})")
        except:
            table.add_row(f"{role.upper()} VM", "❌ Down", f"{vm_ip}")
            continue
        
        # Check containers on this VM
        try:
            ps_cmd = f"docker ps -a --filter name={project}- --format '{{{{.Names}}}}|{{{{.Status}}}}|{{{{.State}}}}'"
            containers = ssh_command(host=vm_ip, user=ssh_user, key_path=ssh_key, cmd=ps_cmd)
            
            for line in containers.strip().split("\n"):
                if not line:
                    continue
                
                parts = line.split("|")
                if len(parts) < 3:
                    continue
                
                container_name = parts[0]
                status_text = parts[1]
                state = parts[2]
                
                # Extract service name (e.g., cheapa-api -> api)
                service_match = re.match(rf"{project}-(\w+)", container_name)
                if not service_match:
                    continue
                
                service = service_match.group(1)
                
                # Determine status icon
                if state == "running":
                    if "healthy" in status_text.lower():
                        icon = "✅"
                        status = "Running"
                    elif "unhealthy" in status_text.lower():
                        icon = "⚠️"
                        status = "Unhealthy"
                    else:
                        icon = "✅"
                        status = "Running"
                else:
                    icon = "❌"
                    status = "Down"
                
                # Clean up status text
                status_display = status_text.replace("Up ", "").replace("Exited ", "Exit ")
                
                table.add_row(f"  {service}", f"{icon} {status}", status_display)
        
        except Exception as e:
            table.add_row(f"  containers", "❌ Error", str(e))
    
    console.print(table)
    
    # Show access URLs
    console.print("\n[bold cyan]🌐 Access URLs:[/bold cyan]")
    
    for app_name, app_config in apps.items():
        vm_role = app_config.get("vm", "core")
        port = app_config.get("external_port") or app_config.get("port")
        
        if vm_role in vms and port:
            vm_ip = vms[vm_role]["ip"]
            console.print(f"{app_name.capitalize():12} http://{vm_ip}:{port}")
    
    console.print()
