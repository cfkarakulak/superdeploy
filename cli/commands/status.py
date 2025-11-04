"""SuperDeploy CLI - Status command"""

import os
import click
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header
from cli.utils import get_project_root, ssh_command, load_env
from cli.logger import DeployLogger

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def status(project, verbose):
    """
    Show infrastructure and application status

    Displays:
    - VM status per role
    - Container status per VM
    - Application health
    """
    if not verbose:
        show_header(
            title="Infrastructure Status",
            project=project,
            console=console,
        )

    logger = DeployLogger(project, "status", verbose=verbose)

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    # Load project config
    logger.step("Loading project configuration")
    from cli.core.config_loader import ConfigLoader

    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        config = project_config.raw_config
        logger.success("Configuration loaded")
    except FileNotFoundError:
        logger.log_error(f"Project '{project}' not found")
        raise SystemExit(1)
    except ValueError as e:
        logger.log_error(f"Error loading config: {e}")
        raise SystemExit(1)

    # Load .env to get VM IPs
    env = load_env(project=project)

    # Get VMs from config and their IPs from .env
    vms_config = config.get("vms", {})
    vms = {}

    for role in vms_config.keys():
        # Get IP from .env (e.g., API_0_EXTERNAL_IP)
        ip_key = f"{role.upper()}_0_EXTERNAL_IP"
        if ip_key in env:
            vms[role] = {
                "ip": env[ip_key],
                "internal_ip": env.get(f"{role.upper()}_0_INTERNAL_IP", ""),
            }

    if not vms:
        logger.warning("No VM IPs found in .env")
        logger.log(f"Run: superdeploy up -p {project}")
        raise SystemExit(1)

    # Get apps and their VM assignments
    apps = config.get("apps", {})

    logger.step("Checking VM and container status")

    # Create table
    table = Table(
        title=f"{project} - Infrastructure Status",
        title_justify="left",
        padding=(0, 1),
    )
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"

    # Check each VM and its containers
    for role, vm_info in sorted(vms.items()):
        vm_ip = vm_info["ip"]

        # Check VM uptime
        try:
            uptime_cmd = "uptime -p"
            uptime = ssh_command(
                host=vm_ip, user=ssh_user, key_path=ssh_key, cmd=uptime_cmd
            )
            uptime = uptime.strip().replace("up ", "")
            table.add_row(f"{role.upper()} VM", "✅ Running", f"{vm_ip} ({uptime})")
        except Exception as e:
            table.add_row(f"{role.upper()} VM", "❌ Down", f"{vm_ip} - {str(e)[:30]}")
            continue

        # Check containers on this VM
        try:
            ps_cmd = f'docker ps -a --filter name={project}- --format "{{{{.Names}}}}|{{{{.Status}}}}|{{{{.State}}}}"'
            containers = ssh_command(
                host=vm_ip, user=ssh_user, key_path=ssh_key, cmd=ps_cmd
            )

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
                import re

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
                status_display = status_text.replace("Up ", "").replace(
                    "Exited ", "Exit "
                )

                table.add_row(f"  {service}", f"{icon} {status}", status_display)

        except Exception as e:
            table.add_row("  containers", "❌ Error", str(e)[:40])

    console.print(table)
    logger.success("Status check complete")

    # Show access URLs
    if not verbose:
        console.print("\n[bold cyan]🌐 Access URLs:[/bold cyan]")

        for app_name, app_config in apps.items():
            vm_role = app_config.get("vm", "core")
            port = app_config.get("external_port") or app_config.get("port")

            if vm_role in vms and port:
                vm_ip = vms[vm_role]["ip"]
                console.print(f"{app_name.capitalize():12} http://{vm_ip}:{port}")

        console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
