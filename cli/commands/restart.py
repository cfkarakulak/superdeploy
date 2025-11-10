"""SuperDeploy CLI - Restart command (Refactored)"""

import click
from cli.base import ProjectCommand
from cli.constants import CONTAINER_NAME_FORMAT


class RestartCommand(ProjectCommand):
    """Restart application container."""

    def __init__(self, project_name: str, app_name: str, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name

    def execute(self) -> None:
        """Execute restart command."""
        self.show_header(
            title="Restart Application", project=self.project_name, app=self.app_name
        )

        # Require deployment
        self.require_deployment()

        # Initialize logger
        logger = self.init_logger(self.project_name, f"restart-{self.app_name}")

        logger.step("Finding Application")

        # Get VM and IP
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)
            logger.log(f"App '{self.app_name}' running on {vm_name} ({vm_ip})")
        except Exception as e:
            self.handle_error(e, f"Could not find VM for app '{self.app_name}'")
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        logger.step("Restarting Container")

        container_name = CONTAINER_NAME_FORMAT.format(
            project=self.project_name, app=self.app_name
        )

        try:
            # Restart container
            result = ssh_service.execute_command(
                vm_ip, f"docker restart {container_name}", check=True
            )

            logger.log(f"✓ Container restarted: {container_name}")

            # Check container status
            result = ssh_service.execute_command(
                vm_ip,
                f"docker ps --filter name={container_name} --format '{{{{.Status}}}}'",
                check=True,
            )

            status = result.stdout.strip()
            if status:
                logger.log(f"Status: {status}")

            logger.success("Application restarted successfully")

            if not self.verbose:
                self.console.print("\n[color(248)]Application restarted.[/color(248)]")
                self.console.print("\n[dim]Monitor logs:[/dim]")
                self.console.print(
                    f"  [cyan]superdeploy :logs{self.project_name} -a {self.app_name} -f[/cyan]"
                )
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

        except Exception as e:
            self.handle_error(e, "Failed to restart container")
            raise SystemExit(1)


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def restart(project, app, verbose):
    """
    Restart an application container

    \b
    Example:
      superdeploy cheapa:restart -a api
    """
    cmd = RestartCommand(project, app, verbose=verbose)
    cmd.run()
