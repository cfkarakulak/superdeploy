"""
Restart Command

Restart application containers with status verification.
"""

import click
from dataclasses import dataclass

from cli.base import ProjectCommand
from cli.exceptions import DeploymentError


@dataclass
class RestartOptions:
    """Options for restart command."""

    app_name: str


class RestartCommand(ProjectCommand):
    """
    Restart application container.

    Features:
    - Graceful container restart
    - Status verification
    - Automatic logging
    """

    def __init__(
        self,
        project_name: str,
        options: RestartOptions,
        verbose: bool = False,
        json_output: bool = False,
    ):
        """
        Initialize restart command.

        Args:
            project_name: Name of the project
            options: RestartOptions with configuration
            verbose: Whether to show verbose output
            json_output: Whether to output in JSON format
        """
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.options = options

    def execute(self) -> None:
        """Execute restart command."""
        self.show_header(
            title="Restart Application",
            project=self.project_name,
            app=self.options.app_name,
        )

        self.require_deployment()

        # Initialize logger
        logger = self.init_logger(self.project_name, f"restart-{self.options.app_name}")

        if logger:
            logger.step("Finding Application")

        # Get VM and IP for app
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.options.app_name)
            if logger:
                logger.log(
                    f"App '{self.options.app_name}' running on {vm_name} ({vm_ip})"
                )
        except Exception as e:
            self.handle_error(e, f"Could not find VM for app '{self.options.app_name}'")
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        if logger:
            logger.step("Restarting Container")

        # Service name for docker compose (e.g., "api-web")
        service_name = f"{self.options.app_name}-web"
        compose_dir = f"/opt/superdeploy/projects/{self.project_name}/compose"

        try:
            # Restart using docker compose
            result = ssh_service.execute_command(
                vm_ip, f"cd {compose_dir} && docker compose restart {service_name}"
            )

            if result.is_failure:
                raise DeploymentError(
                    f"Failed to restart service: {service_name}",
                    context=result.stderr,
                )

            if logger:
                logger.log(f"✓ Service restarted: {service_name}")

            # Check container status using docker compose
            status_result = ssh_service.execute_command(
                vm_ip,
                f"cd {compose_dir} && docker compose ps {service_name} --format '{{{{.Status}}}}'",
            )

            if status_result.is_success and status_result.stdout.strip():
                status = status_result.stdout.strip()
                if logger:
                    logger.log(f"Status: {status}")
            else:
                if logger:
                    logger.warning("Could not verify container status")

            if logger:
                logger.success("Application restarted successfully")

            self._print_summary(logger)

        except DeploymentError:
            raise
        except Exception as e:
            self.handle_error(e, "Failed to restart container")
            raise SystemExit(1)

    def _print_summary(self, logger) -> None:
        """Print restart summary."""
        if not self.verbose:
            self.console.print("\n[color(248)]Application restarted.[/color(248)]")
            self.console.print("\n[dim]Monitor logs:[/dim]")
            self.console.print(
                f"  [cyan]superdeploy {self.project_name}:logs -a {self.options.app_name}[/cyan]"
            )
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def restart(project, app, verbose, json_output):
    """
    Restart an application container

    This command performs a graceful restart of the specified application
    container and verifies its status after restart.

    Examples:
        # Restart API application
        superdeploy cheapa:restart -a api

        # Restart with verbose output
        superdeploy cheapa:restart -a storefront -v
    """
    options = RestartOptions(app_name=app)
    cmd = RestartCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
