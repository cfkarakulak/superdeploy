"""SuperDeploy CLI - Tunnel command (Refactored)"""

import click
import subprocess
from rich.table import Table
from cli.base import ProjectCommand
from cli.constants import TUNNEL_PORT_MAPPINGS

# Extended port mappings with connection strings
TUNNEL_SERVICE_INFO = {
    "postgres": {
        "name": "PostgreSQL",
        "connection": "psql -h localhost -p 15432 -U postgres",
    },
    "rabbitmq": {
        "name": "RabbitMQ Management UI",
        "connection": "http://localhost:25672",
    },
    "redis": {
        "name": "Redis",
        "connection": "redis-cli -h localhost -p 16380",
    },
    "grafana": {
        "name": "Grafana",
        "connection": "http://localhost:3001",
    },
    "prometheus": {
        "name": "Prometheus",
        "connection": "http://localhost:9091",
    },
}


class TunnelCommand(ProjectCommand):
    """Create SSH tunnels to project services."""

    def __init__(
        self,
        project_name: str,
        service: str = None,
        all_services: bool = False,
        list_services: bool = False,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.service = service
        self.all_services = all_services
        self.list_services = list_services

    def execute(self) -> None:
        """Execute tunnel command."""
        # List available services
        if self.list_services:
            self._show_available_services()
            return

        # Validate input
        if not self.service and not self.all_services:
            self.exit_with_error(
                "Specify a service or use --all\n\n"
                "Available services:\n"
                + "\n".join(f"  - {k}" for k in TUNNEL_SERVICE_INFO.keys())
            )

        # Require deployment
        self.require_deployment()

        # Determine which services to tunnel
        services_to_tunnel = self._get_services_to_tunnel()

        # Get VM IP (prefer core-0)
        try:
            vm_ip = self.state_service.get_vm_ip_by_role("core", index=0)
        except Exception:
            self.exit_with_error("Could not find core VM IP in state")

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Show header
        self.show_header(
            title="SSH Tunnel Manager",
            project=self.project_name,
            details={
                "VM": vm_ip,
                "Services": ", ".join(
                    [TUNNEL_SERVICE_INFO[s]["name"] for s in services_to_tunnel]
                ),
            },
        )

        # Build SSH tunnel command
        tunnel_args = []
        for svc in services_to_tunnel:
            local_port, remote_port = TUNNEL_PORT_MAPPINGS[svc]
            tunnel_args.extend(["-L", f"{local_port}:localhost:{remote_port}"])

        ssh_cmd = (
            [
                "ssh",
                "-i",
                str(ssh_service.config.key_path_expanded),
                "-N",  # No remote command
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
            ]
            + tunnel_args
            + [f"{ssh_service.config.user}@{vm_ip}"]
        )

        # Show connection info
        self._show_active_tunnels(services_to_tunnel)

        self.console.print("\n[bold green]✓ Tunnels active![/bold green]")
        self.console.print("[dim]Press Ctrl+C to stop tunnels...[/dim]\n")

        # Print detailed connection information
        self.console.print("[bold cyan]📋 Connection Details:[/bold cyan]\n")

        for svc in services_to_tunnel:
            local_port, _ = TUNNEL_PORT_MAPPINGS[svc]
            svc_info = TUNNEL_SERVICE_INFO[svc]

            self.console.print(f"[bold yellow]{svc_info['name']}:[/bold yellow]")

            if svc == "postgres":
                try:
                    from cli.database import get_db_session
                    from sqlalchemy import text

                    db = get_db_session()
                    try:
                        # Try to get from addon_secrets first
                        result = db.execute(
                            text("""
                                SELECT key, value 
                                FROM addon_secrets 
                                WHERE project_name=:project 
                                AND addon_type='postgres' 
                                AND addon_instance='postgres'
                            """),
                            {"project": self.project_name},
                        )
                        secrets = {row[0]: row[1] for row in result}

                        db_user = secrets.get("USER", "postgres")
                        db_pass = secrets.get("PASSWORD", "password")
                        db_name = secrets.get("DATABASE", f"{self.project_name}_db")
                    finally:
                        db.close()

                    self.console.print("  [green]Host:[/green] localhost")
                    self.console.print(f"  [green]Port:[/green] {local_port}")
                    self.console.print(f"  [green]User:[/green] {db_user}")
                    self.console.print(f"  [green]Password:[/green] {db_pass}")
                    self.console.print(f"  [green]Database:[/green] {db_name}")
                    self.console.print(
                        "\n  [bold cyan]📦 TablePlus Connection:[/bold cyan]"
                    )
                    self.console.print("  [dim]Connection Type:[/dim] PostgreSQL")
                    self.console.print("  [dim]Copy this string:[/dim]")
                    self.console.print(
                        f"  [green]postgresql://{db_user}:{db_pass}@localhost:{local_port}/{db_name}[/green]\n"
                    )
                except Exception as e:
                    self.console.print(
                        f"  [yellow]Warning: Could not fetch credentials: {e}[/yellow]"
                    )
                    self.console.print(f"  {svc_info['connection']}\n")

            elif svc == "rabbitmq":
                try:
                    from cli.database import get_db_session
                    from sqlalchemy import text

                    db = get_db_session()
                    try:
                        # Try to get from addon_secrets first
                        result = db.execute(
                            text("""
                                SELECT key, value 
                                FROM addon_secrets 
                                WHERE project_name=:project 
                                AND addon_type='rabbitmq' 
                                AND addon_instance='rabbitmq'
                            """),
                            {"project": self.project_name},
                        )
                        secrets = {row[0]: row[1] for row in result}

                        rmq_user = secrets.get("USER", "guest")
                        rmq_pass = secrets.get("PASSWORD", "guest")
                    finally:
                        db.close()

                    self.console.print(
                        f"  [green]Management UI:[/green] http://localhost:{local_port}"
                    )
                    self.console.print(f"  [green]User:[/green] {rmq_user}")
                    self.console.print(f"  [green]Password:[/green] {rmq_pass}")
                    self.console.print("  [green]AMQP Port:[/green] 5672")
                    self.console.print(
                        "\n  [bold cyan]📦 TablePlus Connection:[/bold cyan]"
                    )
                    self.console.print("  [dim]Connection Type:[/dim] RabbitMQ")
                    self.console.print(
                        f"  [dim]Management URL:[/dim] http://localhost:{local_port}\n"
                    )
                except Exception as e:
                    self.console.print(
                        f"  [yellow]Warning: Could not fetch credentials: {e}[/yellow]"
                    )
                    self.console.print(f"  {svc_info['connection']}\n")
            else:
                self.console.print(f"  {svc_info['connection']}\n")

        # Run SSH tunnel (blocking)
        try:
            subprocess.run(ssh_cmd, check=True)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]🛑 Tunnels closed[/yellow]")
        except subprocess.CalledProcessError as e:
            self.handle_error(e, "SSH tunnel failed")
            raise SystemExit(1)

    def _get_services_to_tunnel(self) -> list[str]:
        """Determine which services to tunnel."""
        if self.all_services:
            return list(TUNNEL_SERVICE_INFO.keys())

        if self.service in TUNNEL_SERVICE_INFO:
            return [self.service]

        self.exit_with_error(
            f"Unknown service: {self.service}\n\n"
            "Available services:\n"
            + "\n".join(f"  - {k}" for k in TUNNEL_SERVICE_INFO.keys())
        )

    def _show_active_tunnels(self, services: list[str]) -> None:
        """Show table of active tunnels."""
        table = Table(
            title="Active Tunnels",
            show_header=True,
            title_justify="left",
            padding=(0, 1),
        )
        table.add_column("Service", style="cyan")
        table.add_column("Local Port", style="green")
        table.add_column("Connection", style="yellow")

        for svc in services:
            info = TUNNEL_SERVICE_INFO[svc]
            local_port, _ = TUNNEL_PORT_MAPPINGS[svc]
            table.add_row(info["name"], str(local_port), info["connection"])

        self.console.print("\n")
        self.console.print(table)

    def _show_available_services(self) -> None:
        """Show table of available services."""
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

        for svc, info in TUNNEL_SERVICE_INFO.items():
            local_port, remote_port = TUNNEL_PORT_MAPPINGS[svc]
            table.add_row(svc, info["name"], str(local_port), str(remote_port))

        self.console.print(table)


@click.command()
@click.argument("service", required=False)
@click.option("--all", "all_services", is_flag=True, help="Tunnel all services")
@click.option("--list", "list_services", is_flag=True, help="List available services")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def tunnel(project, service, all_services, list_services, verbose, json_output):
    """
    Create SSH tunnels to access database/addon services securely

    \b
    Examples:
      superdeploy cheapa:tunnel postgres
      superdeploy cheapa:tunnel rabbitmq
      superdeploy cheapa:tunnel --all
      superdeploy cheapa:tunnel --list
    """
    cmd = TunnelCommand(
        project, service, all_services, list_services, verbose, json_output=json_output
    )
    cmd.run()
