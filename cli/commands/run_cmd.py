"""SuperDeploy CLI - Run command (Refactored)"""

import click
from cli.base import ProjectCommand
from cli.constants import CONTAINER_NAME_FORMAT


class RunCommand(ProjectCommand):
    """Execute command in application container."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        command: str,
        interactive: bool = False,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.command = command
        self.interactive = interactive

    def execute(self) -> None:
        """Execute run command."""
        if not self.verbose:
            self.show_header(
                title="Run Command",
                project=self.project_name,
                app=self.app_name,
                details={
                    "Command": self.command,
                    "Interactive": "Yes" if self.interactive else "No",
                },
            )

        # Require deployment
        self.require_deployment()

        # Initialize logger (unless interactive mode)
        if not self.interactive:
            logger = self.init_logger(self.project_name, f"run-{self.app_name}")
            logger.step("Finding Application")

        # Get VM and IP
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)

            if not self.interactive:
                logger.log(f"App '{self.app_name}' running on {vm_name} ({vm_ip})")

        except Exception as e:
            self.handle_error(e, f"Could not find VM for app '{self.app_name}'")
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Build container name
        container_name = CONTAINER_NAME_FORMAT.format(
            project=self.project_name, app=self.app_name
        )

        if not self.interactive:
            logger.step("Executing Command")
            logger.log(f"Container: {container_name}")
            logger.log(f"Command: {self.command}")

        try:
            if self.interactive:
                # Interactive mode (with TTY)
                exit_code = ssh_service.docker_exec(
                    vm_ip, container_name, self.command, interactive=True
                )

                if exit_code != 0:
                    raise SystemExit(exit_code)

            else:
                # Non-interactive mode
                result = ssh_service.docker_exec(
                    vm_ip, container_name, self.command, interactive=False
                )

                # Display output
                if result.stdout:
                    self.console.print("\n[bold cyan]Output:[/bold cyan]")
                    self.console.print(result.stdout)

                if result.stderr:
                    self.console.print("\n[bold yellow]Errors:[/bold yellow]")
                    self.console.print(result.stderr)

                if result.returncode == 0:
                    logger.success("Command executed successfully")
                else:
                    logger.log_error(
                        f"Command failed with exit code: {result.returncode}"
                    )
                    raise SystemExit(result.returncode)

                if not self.verbose:
                    self.console.print(
                        f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n"
                    )

        except Exception as e:
            if not self.interactive:
                self.handle_error(e, "Command execution failed")
            raise SystemExit(1)


@click.command(name="run")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode (with TTY)")
@click.argument("app")
@click.argument("command")
def run(project, app, command, verbose, interactive):
    """
    Run command in application container

    \b
    Examples:
      superdeploy run api "python manage.py migrate"
      superdeploy run api "bash" -i                    # Interactive shell
      superdeploy run services "npm run test"

    \b
    Interactive mode:
      Use -i flag for commands that need user input or TTY
      (e.g., bash, psql, redis-cli)
    """
    cmd = RunCommand(project, app, command, interactive=interactive, verbose=verbose)
    cmd.run()
