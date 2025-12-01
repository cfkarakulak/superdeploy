"""
Run Command

Execute commands in application containers.
"""

import click
from dataclasses import dataclass
from rich.text import Text

from cli.base import ProjectCommand
from cli.services.ssh_service import DockerExecOptions


@dataclass
class RunCommandOptions:
    """Options for run command."""

    app_name: str
    command: str
    interactive: bool = False


class RunCommand(ProjectCommand):
    """
    Execute command in application container.

    Features:
    - Interactive and non-interactive modes
    - Output capture and display
    - Exit code propagation
    """

    def __init__(
        self,
        project_name: str,
        options: RunCommandOptions,
        verbose: bool = False,
        json_output: bool = False,
    ):
        """
        Initialize run command.

        Args:
            project_name: Name of the project
            options: RunCommandOptions with configuration
            verbose: Whether to show verbose output
            json_output: Whether to output in JSON format
        """
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.options = options
        self.logger = None

    def execute(self) -> None:
        """Execute run command."""
        if not self.verbose:
            self.show_header(
                title="Run Command",
                project=self.project_name,
                app=self.options.app_name,
                details={
                    "Command": self.options.command,
                    "Interactive": "Yes" if self.options.interactive else "No",
                },
            )

        self.require_deployment()

        # Initialize logger (unless interactive mode)
        if not self.options.interactive:
            self.logger = self.init_logger(
                self.project_name, f"run-{self.options.app_name}"
            )
            self.logger.step("Finding Application")

        # Get VM and IP for app
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.options.app_name)

            if not self.options.interactive and self.logger:
                self.logger.log(
                    f"App '{self.options.app_name}' running on {vm_name} ({vm_ip})"
                )

        except Exception as e:
            self.handle_error(e, f"Could not find VM for app '{self.options.app_name}'")
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Service name for docker compose (e.g., "api-web")
        service_name = f"{self.options.app_name}-web"

        if self.options.interactive:
            self._execute_interactive(ssh_service, vm_ip, service_name)
        else:
            self._execute_non_interactive(ssh_service, vm_ip, service_name)

    def _execute_interactive(self, ssh_service, vm_ip: str, service_name: str) -> None:
        """
        Execute command in interactive mode.

        Args:
            ssh_service: SSH service instance
            vm_ip: VM IP address
            service_name: Docker Compose service name
        """
        try:
            exec_options = DockerExecOptions(interactive=True, tty=True)
            result = ssh_service.docker_compose_exec(
                vm_ip,
                self.project_name,
                service_name,
                self.options.command,
                options=exec_options,
            )

            if result.returncode != 0:
                raise SystemExit(result.returncode)

        except Exception:
            # Don't log in interactive mode
            raise SystemExit(1)

    def _execute_non_interactive(
        self, ssh_service, vm_ip: str, service_name: str
    ) -> None:
        """
        Execute command in non-interactive mode.

        Args:
            ssh_service: SSH service instance
            vm_ip: VM IP address
            service_name: Docker Compose service name
        """
        if not self.logger:
            return

        self.logger.step("Executing Command")
        self.logger.log(f"Service: {service_name}")
        self.logger.log(f"Command: {self.options.command}")

        try:
            result = ssh_service.docker_compose_exec(
                vm_ip, self.project_name, service_name, self.options.command
            )

            # Display output with ANSI color support
            if result.stdout:
                self.console.print("\n[bold cyan]Output:[/bold cyan]")
                # Use Text.from_ansi() to properly render ANSI color codes
                self.console.print(Text.from_ansi(result.stdout))

            if result.stderr:
                self.console.print("\n[bold yellow]Errors:[/bold yellow]")
                self.console.print(Text.from_ansi(result.stderr))

            if result.is_success:
                self.logger.success("Command executed successfully")
            else:
                self.logger.log_error(
                    f"Command failed with exit code: {result.returncode}"
                )
                raise SystemExit(result.returncode)

            if not self.verbose:
                self.console.print(
                    f"\n[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )

        except Exception as e:
            self.handle_error(e, "Command execution failed")
            raise SystemExit(1)


@click.command(name="run")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode (with TTY)")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.argument("app")
@click.argument("command")
def run(project, app, command, verbose, interactive, json_output):
    """
    Run command in application container

    Execute arbitrary commands inside running application containers.
    Supports both interactive (with TTY) and non-interactive modes.

    Examples:
        # Run database migrations
        superdeploy cheapa:run api "python manage.py migrate"

        # Interactive bash shell
        superdeploy cheapa:run api "bash" -i

        # Run tests
        superdeploy cheapa:run services "npm run test"

        # Access PostgreSQL
        superdeploy cheapa:run api "psql -U user database" -i

    Interactive mode:
        Use -i flag for commands that need user input or TTY allocation
        (e.g., bash, psql, redis-cli, python REPL)
    """
    options = RunCommandOptions(
        app_name=app,
        command=command,
        interactive=interactive,
    )

    cmd = RunCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
