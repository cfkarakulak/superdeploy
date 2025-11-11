"""
Process Status Command

Show running application containers with replica counts (Heroku-like).
"""

import click
from rich.table import Table

from cli.base import ProjectCommand


class ProcessStatusCommand(ProjectCommand):
    """Show application process status with replicas."""

    def execute(self) -> None:
        """Execute ps command."""
        self.show_header(
            title="Application Processes",
            project=self.project_name,
            subtitle="Running containers and replicas",
        )

        # Load config
        config = self.config_service.get_raw_config(self.project_name)
        apps = config.get("apps", {})

        if not apps:
            self.console.print("[yellow]No applications configured[/yellow]")
            return

        # Create table
        table = Table(
            show_header=True,
            header_style="bold cyan",
            title=f"{self.project_name} processes",
        )
        table.add_column("App", style="cyan", no_wrap=True)
        table.add_column("Type", style="white")
        table.add_column("Replicas", style="yellow", justify="center")
        table.add_column("Port", style="green", justify="center")
        table.add_column("VM", style="magenta")
        table.add_column("Status", style="blue")

        for app_name, app_config in apps.items():
            # Determine app type (auto-detect if not specified)
            app_type = app_config.get("type")
            if not app_type:
                app_type = "web" if app_config.get("port") else "worker"

            # Get replicas
            replicas = app_config.get("replicas", 1)

            # Get port
            port = str(app_config.get("port", "-"))

            # Get VM
            vm = app_config.get("vm", "app")

            # Get status (placeholder - would need SSH to VM to check actual status)
            status = "configured"  # TODO: Check actual Docker container status

            table.add_row(app_name, app_type, str(replicas), port, vm, status)

        self.console.print(table)

        # Summary
        total_replicas = sum(app.get("replicas", 1) for app in apps.values())
        self.console.print(
            f"\n[dim]Total apps: {len(apps)} | Total replicas: {total_replicas}[/dim]"
        )

        # Show scaling examples
        self.console.print("\n[bold]Scale commands:[/bold]")
        if apps:
            first_app = list(apps.keys())[0]
            self.console.print(
                f"  [cyan]superdeploy {self.project_name}:scale {first_app}=3[/cyan]"
            )


@click.command(name="ps")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def ps(project, verbose):
    """
    Show application processes and replicas (Heroku-like)

    Displays all configured applications with their type, replica count,
    port, and deployment status.

    Examples:
        superdeploy cheapa:ps
        superdeploy myproject:ps -v
    """
    cmd = ProcessStatusCommand(project, verbose=verbose)
    cmd.run()
