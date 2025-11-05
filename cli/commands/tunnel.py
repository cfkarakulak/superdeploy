"""
SSH Tunnel Management for SuperDeploy

Create secure SSH tunnels to access database/addon services running on VMs.
Uses port mapping to avoid conflicts with local services.
"""

import click
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header

console = Console()

# Port mapping: remote_port → local_port (to avoid conflicts)
PORT_MAPPINGS = {
    "postgres": {
        "remote": 5432,
        "local": 15432,
        "name": "PostgreSQL",
        "connection": "psql -h localhost -p 15432 -U postgres",
    },
    "rabbitmq": {
        "remote": 15672,  # Management UI
        "local": 25672,
        "name": "RabbitMQ Management UI",
        "connection": "http://localhost:25672",
    },
    "rabbitmq-amqp": {
        "remote": 5672,  # AMQP protocol
        "local": 5673,
        "name": "RabbitMQ AMQP",
        "connection": "amqp://localhost:5673",
    },
    "redis": {
        "remote": 6379,
        "local": 16379,
        "name": "Redis",
        "connection": "redis-cli -h localhost -p 16379",
    },
    "mongodb": {
        "remote": 27017,
        "local": 37017,
        "name": "MongoDB",
        "connection": "mongosh mongodb://localhost:37017",
    },
}


@click.command()
@click.option("-p", "--project", required=True, help="Project name")
@click.argument("service", required=False)
@click.option("--all", "all_services", is_flag=True, help="Tunnel all services")
@click.option("--list", "list_services", is_flag=True, help="List available services")
def tunnel(project, service, all_services, list_services):
    """
    Create SSH tunnels to access database/addon services securely.

    Examples:
        superdeploy tunnel -p cheapa postgres
        superdeploy tunnel -p cheapa rabbitmq
        superdeploy tunnel -p cheapa --all
        superdeploy tunnel -p cheapa --list
    """

    # List available services
    if list_services:
        show_available_services()
        return

    # Validate input
    if not service and not all_services:
        console.print("[red]❌ Error: Specify a service or use --all[/red]")
        console.print("\n[dim]Available services:[/dim]")
        show_available_services()
        sys.exit(1)

    # Load project config
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
    except FileNotFoundError:
        console.print(f"[red]❌ Project '{project}' not found[/red]")
        sys.exit(1)

    # Get VM IP (find first VM with services)
    from dotenv import dotenv_values

    env_file = projects_dir / project / ".env"
    if not env_file.exists():
        console.print(f"[red]❌ Project .env not found: {env_file}[/red]")
        console.print(
            "[yellow]Run '[red]superdeploy up -p {project}[/red]' first[/yellow]"
        )
        sys.exit(1)

    env = dotenv_values(env_file)

    # Find VM IP (prefer core VM, fallback to any VM)
    vm_ip = None
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP"):
            if "CORE" in key:
                vm_ip = value
                break
            elif not vm_ip:
                vm_ip = value

    if not vm_ip:
        console.print("[red]❌ No VM IP found in .env[/red]")
        console.print(
            "[yellow]Run '[red]superdeploy up -p {project}[/red]' first[/yellow]"
        )
        sys.exit(1)

    # Get SSH config from project config
    ssh_config = project_config.raw_config.get("cloud", {}).get("ssh", {})
    ssh_user = ssh_config.get("user", "superdeploy")
    ssh_key = Path(ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")).expanduser()

    # Determine which services to tunnel
    services_to_tunnel = []

    if all_services:
        # Tunnel all available services
        services_to_tunnel = list(PORT_MAPPINGS.keys())
    else:
        # Handle special cases
        if service == "rabbitmq":
            # For RabbitMQ, open both UI and AMQP
            services_to_tunnel = ["rabbitmq", "rabbitmq-amqp"]
        elif service in PORT_MAPPINGS:
            services_to_tunnel = [service]
        else:
            console.print(f"[red]❌ Unknown service: {service}[/red]")
            console.print("\n[dim]Available services:[/dim]")
            show_available_services()
            sys.exit(1)

    # Show banner
    show_header(
        title="SSH Tunnel Manager",
        project=project,
        details={
            "VM": vm_ip,
            "Services": ", ".join(
                [PORT_MAPPINGS[s]["name"] for s in services_to_tunnel]
            ),
        },
        console=console,
    )

    # Build SSH tunnel commands
    tunnel_commands = []
    for svc in services_to_tunnel:
        mapping = PORT_MAPPINGS[svc]
        tunnel_commands.append(f"-L {mapping['local']}:localhost:{mapping['remote']}")

    # Build full SSH command
    ssh_cmd = [
        "ssh",
        "-i",
        str(ssh_key),
        "-N",  # No remote command
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]

    # Add all tunnel mappings
    for tunnel in tunnel_commands:
        ssh_cmd.extend(tunnel.split())

    # Add destination
    ssh_cmd.append(f"{ssh_user}@{vm_ip}")

    # Show connection info
    table = Table(
        title="Active Tunnels",
        show_header=True,
        title_justify="left",
        padding=(0, 1),
    )
    table.add_column("Service", style="cyan")
    table.add_column("Local Port", style="green")
    table.add_column("Connection", style="yellow")

    for svc in services_to_tunnel:
        mapping = PORT_MAPPINGS[svc]
        table.add_row(mapping["name"], str(mapping["local"]), mapping["connection"])

    console.print("\n")
    console.print(table)
    console.print("\n[bold green]✓ Tunnels active![/bold green]")
    console.print("[dim]Press Ctrl+C to stop tunnels...[/dim]\n")

    # Run SSH tunnel (blocking)
    try:
        subprocess.run(ssh_cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Tunnels closed[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ SSH tunnel failed: {e}[/red]")
        sys.exit(1)


def show_available_services():
    """Show table of available services"""
    table = Table(
        title="Available Services",
        show_header=True,
        title_justify="left",
        padding=(0, 1),
    )
    table.add_column("Service", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Local Port", style="green")
    table.add_column("Remote Port", style="yellow")

    # Group services (skip rabbitmq-amqp, it's included in rabbitmq)
    services = {k: v for k, v in PORT_MAPPINGS.items() if k != "rabbitmq-amqp"}

    for svc, mapping in services.items():
        table.add_row(
            svc, mapping["name"], str(mapping["local"]), str(mapping["remote"])
        )

    console.print(table)
    console.print(
        "\n[dim]Note: 'rabbitmq' opens both UI (25672) and AMQP (15672)[/dim]"
    )
