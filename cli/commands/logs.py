"""SuperDeploy CLI - Logs command (Refactored)"""

import click
from cli.base import ProjectCommand


class LogsCommand(ProjectCommand):
    """View application logs."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        follow: bool = False,
        lines: int = 100,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.follow = follow
        self.lines = lines

    def execute(self) -> None:
        """Execute logs command."""
        self.show_header(
            title="Application Logs",
            project=self.project_name,
            app=self.app_name,
            details={
                "Follow": "Yes" if self.follow else "No",
                "Lines": str(self.lines),
            },
        )

        # Require deployment
        self.require_deployment()

        # Initialize logger
        logger = self.init_logger(self.project_name, f"logs-{self.app_name}")

        logger.step("Loading project configuration")

        # Get VM and IP
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)
            logger.success("Configuration loaded")
            logger.log(f"Found VM: {vm_ip}")
        except Exception as e:
            self.handle_error(e)
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Container name
        container_name = f"{self.project_name}-{self.app_name}"

        try:
            # Stream logs
            logger.step(f"Streaming logs from {self.app_name}")
            logger.log("Press Ctrl+C to stop")

            process = ssh_service.docker_logs(
                vm_ip, container_name, follow=self.follow, tail=self.lines
            )

            # Stream output
            if process.stdout:
                for line in process.stdout:
                    print(line, end="")

            process.wait()

            logger.success("Log streaming complete")
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

        except KeyboardInterrupt:
            logger.warning("Stopped by user")
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
            if process:
                process.terminate()
        except Exception as e:
            self.handle_error(e, "Failed to fetch logs")
            raise SystemExit(1)


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-f", "--follow", is_flag=True, help="Follow logs (tail -f)")
@click.option("-n", "--lines", default=100, help="Number of lines")
@click.option("-e", "--env", "environment", default="production", help="Environment")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def logs(project, app, follow, lines, environment, verbose):
    """
    View application logs

    \b
    Examples:
      superdeploy logs -a api              # Last 100 lines
      superdeploy logs -a api -f           # Follow logs
      superdeploy logs -a api -n 500       # Last 500 lines
    """
    cmd = LogsCommand(project, app, follow=follow, lines=lines, verbose=verbose)
    cmd.run()
