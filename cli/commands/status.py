"""SuperDeploy CLI - Status command"""

import os
import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.utils import load_env, validate_env_vars, ssh_command, get_project_root

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
def status(project):
    """
    Show infrastructure status for addon-based projects

    Displays:
    - VM status
    - Service health (from addons)
    - Container status
    - Monitoring dashboard URL
    """
    env = load_env(project)
    project_root = get_project_root()

    # Load project config using ConfigLoader
    from cli.core.config_loader import ConfigLoader
    
    try:
        projects_dir = project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        project_config_obj = config_loader.load_project(project)
        config = project_config_obj.raw_config
    except FileNotFoundError:
        console.print(f"[red]❌ Project '{project}' not found![/red]")
        console.print(f"[dim]Run: superdeploy init -p {project}[/dim]")
        return
    except ValueError as e:
        console.print(f"[red]❌ Error loading project config: {e}[/red]")
        return

    # Get VMs from project config
    vms_config = config.get('vms', {})
    
    if not vms_config:
        console.print("[yellow]⚠️  No VMs configured in project.yml[/yellow]")
        return
    
    # Find first VM with external IP (usually 'core')
    ssh_host = None
    vm_role = None
    
    for role in vms_config.keys():
        # Try to get external IP for this VM role (index 0)
        ip_var = f"{role.upper()}_0_EXTERNAL_IP"
        if ip_var in env:
            ssh_host = env[ip_var]
            vm_role = role
            break
    
    # Validate environment
    required = ["SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env, required) or not ssh_host:
        console.print("[yellow]⚠️  Limited status (IPs not configured yet)[/yellow]")

        # Show basic info
        table = Table(title=f"{project} - Infrastructure Status (Partial)")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="yellow")

        table.add_row("Configuration", "✅ .env loaded")
        table.add_row("Project Config", "✅ project.yml loaded")
        table.add_row("VMs", "⏳ Not deployed yet")
        
        if not ssh_host:
            console.print(f"\n[dim]💡 Run 'superdeploy up -p {project}' to deploy infrastructure[/dim]")

        console.print(table)
        return

    console.print(f"[cyan]📊 Fetching status for {project}...[/cyan]\n")

    # Create table
    table = Table(title=f"{project} - Infrastructure Status")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    # SSH connection details
    ssh_user = env.get("SSH_USER", "superdeploy")
    ssh_key = os.path.expanduser(env["SSH_KEY_PATH"])

    # Check VMs
    vm_status = _check_vm_status(ssh_host, ssh_user, ssh_key, table)
    
    # Check addons
    _check_addons(config, ssh_host, ssh_user, ssh_key, table, project)
    
    # Check application containers
    _check_app_containers(config, ssh_host, ssh_user, ssh_key, table, project)

    console.print(table)

    # Show access URLs
    _show_access_urls(config, ssh_host, env, vm_status)


def _check_vm_status(ssh_host, ssh_user, ssh_key, table):
    """Check VM status and add to table"""
    vm_reachable = False
    
    try:
        uptime = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd="uptime -p"
        )
        table.add_row("Core VM", "✅ Running", f"{ssh_host} ({uptime})")
        vm_reachable = True
    except Exception as e:
        table.add_row("Core VM", "❌ Unreachable", ssh_host)
    
    return vm_reachable


def _check_addons(config, ssh_host, ssh_user, ssh_key, table, project):
    """Check addons status"""
    # Get addons from new structure
    addons = config.get('addons', {})
    
    if not addons:
        table.add_row("Core Services", "ℹ️  None", "No addons configured")
        return
    
    # Check each addon service
    for service_name in addons.keys():
        container_name = f"{project}-{service_name}"
        
        try:
            # Check if container is running
            status_cmd = f"docker ps --filter name={container_name} --format '{{{{.Status}}}}'"
            status = ssh_command(
                host=ssh_host,
                user=ssh_user,
                key_path=ssh_key,
                cmd=status_cmd
            )
            
            if status.strip():
                # Container is running
                table.add_row(f"  {service_name}", "✅ Running", status.strip())
                
                # Try to get health status if available
                try:
                    health_cmd = f"docker inspect {container_name} --format '{{{{.State.Health.Status}}}}' 2>/dev/null || echo 'no-healthcheck'"
                    health = ssh_command(
                        host=ssh_host,
                        user=ssh_user,
                        key_path=ssh_key,
                        cmd=health_cmd
                    ).strip()
                    
                    if health and health != 'no-healthcheck':
                        if health == 'healthy':
                            table.add_row(f"    └─ health", "✅ Healthy", "")
                        elif health == 'unhealthy':
                            table.add_row(f"    └─ health", "❌ Unhealthy", "")
                        elif health == 'starting':
                            table.add_row(f"    └─ health", "⏳ Starting", "")
                except:
                    pass  # Health check not available
            else:
                # Container not running
                table.add_row(f"  {service_name}", "❌ Down", "Container not found")
        except Exception as e:
            table.add_row(f"  {service_name}", "❌ Error", f"Cannot check: {str(e)[:30]}")


def _check_app_containers(config, ssh_host, ssh_user, ssh_key, table, project):
    """Check application containers status"""
    apps = config.get('apps', {})
    
    if not apps:
        return
    
    table.add_row("", "", "")  # Separator
    
    for app_name in apps.keys():
        container_name = f"{project}-{app_name}"
        
        try:
            # Check if container is running
            status_cmd = f"docker ps --filter name={container_name} --format '{{{{.Status}}}}'"
            status = ssh_command(
                host=ssh_host,
                user=ssh_user,
                key_path=ssh_key,
                cmd=status_cmd
            )
            
            if status.strip():
                table.add_row(f"  {app_name}", "✅ Running", status.strip())
            else:
                table.add_row(f"  {app_name}", "❌ Down", "Container not found")
        except Exception as e:
            table.add_row(f"  {app_name}", "❌ Error", f"Cannot check: {str(e)[:30]}")


def _show_access_urls(config, ssh_host, env, vm_reachable):
    """Show access URLs for services"""
    console.print("\n[cyan]🌐 Access URLs:[/cyan]")
    
    # Forgejo (from addons config)
    addons = config.get('addons', {})
    forgejo_config = addons.get('forgejo', {})
    forgejo_port = forgejo_config.get('port', 3001)
    console.print(f"  Forgejo:    http://{ssh_host}:{forgejo_port}")
    
    # Application URLs
    apps = config.get('apps', {})
    for app_name, app_config in apps.items():
        port = app_config.get('port', 8000)
        # Format app name with proper spacing
        formatted_name = f"{app_name.capitalize()}:"
        console.print(f"  {formatted_name:12} http://{ssh_host}:{port}")
    
    # Monitoring dashboard URL (if monitoring addon is configured)
    if 'monitoring' in addons:
        monitoring_config = addons.get('monitoring', {})
        grafana_port = monitoring_config.get('grafana_port', 3000)
        prometheus_port = monitoring_config.get('prometheus_port', 9090)
        
        console.print(f"\n[cyan]📊 Monitoring:[/cyan]")
        console.print(f"  Grafana:    http://{ssh_host}:{grafana_port}")
        console.print(f"  Prometheus: http://{ssh_host}:{prometheus_port}")
        
        if vm_reachable:
            console.print(f"  [dim]Filter by project: {config.get('project')}[/dim]")
