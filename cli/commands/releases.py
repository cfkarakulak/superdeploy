"""SuperDeploy CLI - Releases command"""

import click
from rich.table import Table
from cli.base import ProjectCommand


class ReleasesCommand(ProjectCommand):
    """Show release history for an app (last 5 releases kept)."""

    def __init__(
        self, project_name: str, app_name: str, limit: int = 10, verbose: bool = False
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.limit = limit

    def execute(self) -> None:
        """Execute releases command."""
        self.show_header(
            title="Deployment History",
            project=self.project_name,
            app=self.app_name,
            details={"Type": "Version Tracking"},
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"releases-{self.app_name}")

        logger.step(f"Fetching deployment history for {self.app_name}")

        # Use version tracking system
        try:
            # Get VM for app
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)

            # Get SSH service
            vm_service = self.ensure_vm_service()
            ssh_service = vm_service.get_ssh_service()

            # Read versions.json from VM
            result = ssh_service.execute_command(
                vm_ip,
                f"cat /opt/superdeploy/projects/{self.project_name}/versions.json 2>/dev/null || echo '{{}}'",
                timeout=5,
            )

            if result.returncode != 0 or not result.stdout.strip():
                self.console.print("[yellow]⚠️  No deployment history found[/yellow]")
                self.console.print(
                    "[dim]Deploy the app first: git push origin production[/dim]\n"
                )
                return

            import json

            versions_data = json.loads(result.stdout)

            if self.app_name not in versions_data:
                self.console.print(
                    f"[yellow]⚠️  No deployment history for {self.app_name}[/yellow]"
                )
                return

            # Get deployment info
            app_version = versions_data[self.app_name]

            # Create deployment history table
            table = Table(
                title=f"Current Deployment - {self.app_name}",
                show_header=True,
                header_style="bold cyan",
                padding=(0, 1),
            )
            table.add_column("Status", style="green", no_wrap=True)
            table.add_column("Version", style="cyan")
            table.add_column("Git SHA", style="yellow")
            table.add_column("Deployed By", style="white")
            table.add_column("Deployed At", style="dim")
            table.add_column("Branch", style="magenta")

            # Current deployment
            deployed_at = app_version.get("deployed_at", "-")
            if "T" in deployed_at:
                deployed_at = deployed_at.replace("T", " ").replace("Z", " UTC")

            table.add_row(
                "● CURRENT",
                app_version.get("version", "-"),
                app_version.get("git_sha", "-")[:7],
                app_version.get("deployed_by", "-"),
                deployed_at,
                app_version.get("branch", "-"),
            )

            self.console.print(table)

            logger.success(f"Deployment history retrieved for {self.app_name}")

            # Show switch instructions
            self.console.print("\n[bold]💡 Switch to any version:[/bold]")
            self.console.print(
                f"   [cyan]superdeploy {self.project_name}:releases:switch -a {self.app_name} -v <git-sha>[/cyan]"
            )
            self.console.print("\n[dim]Available Docker images on DockerHub:[/dim]")
            self.console.print(
                f"   [dim]docker pull <org>/{self.app_name}:<git-sha>[/dim]"
            )
            self.console.print(
                f"   [dim]docker pull <org>/{self.app_name}:latest[/dim]\n"
            )

            if not self.verbose:
                self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")

        except Exception as e:
            logger.log_error(f"Error fetching history: {e}")
            self.console.print(f"[red]❌ Error: {e}[/red]")
            import traceback

            if self.verbose:
                traceback.print_exc()
            if not self.verbose:
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")


@click.command(name="releases:list")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-n", "--limit", default=10, help="Number of releases to show")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def releases_list(project, app, limit, verbose):
    """
    Show release history for an app (last 5 releases kept)

    \b
    Examples:
      superdeploy cheapa:releases:list -a api          # Show all releases
      superdeploy cheapa:releases:list -a api -n 3     # Show last 3

    \b
    Shows:
    - Release timestamp
    - Git SHA
    - Current/Previous status
    - Use 'superdeploy releases:rollback' to change versions
    """
    cmd = ReleasesCommand(project, app, limit=limit, verbose=verbose)
    cmd.run()
