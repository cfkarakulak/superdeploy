"""
Scale Command

Scale VM count for infrastructure roles.
"""

import click
import yaml
from dataclasses import dataclass

from cli.base import ProjectCommand


@dataclass
class ScaleOptions:
    """Options for scale command."""

    target_type: str  # "vm" or "app"
    target_name: str  # vm role or app name
    count: int


class ScaleCommand(ProjectCommand):
    """
    Scale VM count for a role.

    Features:
    - Validate VM role existence
    - Update configuration file
    - Confirmation prompt
    - Safe scaling operations
    """

    def __init__(
        self,
        project_name: str,
        options: ScaleOptions,
        verbose: bool = False,
    ):
        """
        Initialize scale command.

        Args:
            project_name: Name of the project
            options: ScaleOptions with configuration
            verbose: Whether to show verbose output
        """
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.options = options

    def execute(self) -> None:
        """Execute scale command."""
        if self.options.target_type == "app":
            self._scale_app()
        else:
            self._scale_vm()

    def _scale_app(self) -> None:
        """Scale application replicas."""
        self.show_header(
            title="Scale Application",
            project=self.project_name,
            details={
                "App": self.options.target_name,
                "Replicas": str(self.options.count),
            },
        )

        # Initialize logger
        logger = self.init_logger(
            self.project_name, f"scale-app-{self.options.target_name}"
        )

        if logger:

            logger.step("Validating Configuration")

        # Get current app config
        apps_config = self.config_service.get_apps(self.project_name)

        if self.options.target_name not in apps_config:
            available_apps = ", ".join(apps_config.keys())
            self.exit_with_error(
                f"App '{self.options.target_name}' not found in project config\n"
                f"Available apps: {available_apps}"
            )

        current_app_config = apps_config[self.options.target_name]
        current_replicas = current_app_config.get("replicas", 1)
        if logger:
            logger.log(f"Current replicas: {current_replicas}")
        if logger:
            logger.log(f"Target replicas: {self.options.count}")

        if current_replicas == self.options.count:
            self.print_warning(
                f"App '{self.options.target_name}' is already at "
                f"{self.options.count} replica(s)"
            )
            return

        # Confirm scaling action
        action = "scale up" if self.options.count > current_replicas else "scale down"
        message = (
            f"[yellow]{action.title()} {self.options.target_name} from "
            f"{current_replicas} to {self.options.count} replica(s)?[/yellow]"
        )
        if not self.confirm(message, default=False):
            self.print_warning("Scaling cancelled")
            return

        if logger:

            logger.step("Updating Configuration")

        # Update config.yml
        try:
            project_path = self.project_root / "projects" / self.project_name
            config_yml = project_path / "config.yml"

            with open(config_yml, "r") as f:
                config = yaml.safe_load(f)

            config["apps"][self.options.target_name]["replicas"] = self.options.count

            with open(config_yml, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            if logger:

                logger.log(f"✓ Updated {config_yml}")
        except Exception as e:
            self.handle_error(e, "Failed to update configuration")
            raise SystemExit(1)

        if logger:

            logger.step("Next Steps")

        self.console.print("\n[bold yellow]To apply these changes, run:[/bold yellow]")
        self.console.print(f"  [cyan]superdeploy {self.project_name}:up[/cyan]")
        self.console.print()

        if logger:

            logger.success("Configuration updated")

        if not self.verbose:
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _scale_vm(self) -> None:
        """Scale VM infrastructure."""
        self.show_header(
            title="Scale Infrastructure",
            project=self.project_name,
            details={
                "VM Role": self.options.target_name,
                "Count": str(self.options.count),
            },
        )

        # Initialize logger
        logger = self.init_logger(
            self.project_name, f"scale-{self.options.target_name}"
        )

        if logger:

            logger.step("Validating Configuration")

        # Get current VM config
        vms_config = self.config_service.get_vms(self.project_name)

        if self.options.target_name not in vms_config:
            available_roles = ", ".join(vms_config.keys())
            self.exit_with_error(
                f"VM role '{self.options.target_name}' not found in project config\n"
                f"Available roles: {available_roles}"
            )

        current_count = vms_config[self.options.target_name].get("count", 1)
        if logger:
            logger.log(f"Current count: {current_count}")
        if logger:
            logger.log(f"Target count: {self.options.count}")

        if current_count == self.options.count:
            self.print_warning(
                f"VM role '{self.options.target_name}' is already at "
                f"{self.options.count} instance(s)"
            )
            return

        # Confirm scaling action
        if not self._confirm_scaling_vm(current_count):
            self.print_warning("Scaling cancelled")
            return

        if logger:

            logger.step("Updating Configuration")

        # Update config.yml
        try:
            self._update_config_file(logger)
        except Exception as e:
            self.handle_error(e, "Failed to update configuration")
            raise SystemExit(1)

        if logger:

            logger.step("Applying Changes")

        self._print_next_steps()

        if logger:

            logger.success("Configuration updated")

        if not self.verbose:
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _confirm_scaling_vm(self, current_count: int) -> bool:
        """
        Confirm VM scaling action with user.

        Args:
            current_count: Current VM count

        Returns:
            True if user confirms
        """
        action = "scale up" if self.options.count > current_count else "scale down"
        message = (
            f"[yellow]{action.title()} {self.options.target_name} from "
            f"{current_count} to {self.options.count} instance(s)?[/yellow]"
        )
        return self.confirm(message, default=False)

    def _update_config_file(self, logger) -> None:
        """
        Update project configuration file with new VM count.

        Args:
            logger: Logger instance
        """
        project_path = self.project_root / "projects" / self.project_name
        project_yml = project_path / "config.yml"

        with open(project_yml, "r") as f:
            config = yaml.safe_load(f)

        config["vms"][self.options.target_name]["count"] = self.options.count

        with open(project_yml, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        if logger:

            logger.log(f"✓ Updated {project_yml}")

    def _print_next_steps(self) -> None:
        """Print next steps for applying changes."""
        self.console.print("\n[bold yellow]To apply these changes, run:[/bold yellow]")
        self.console.print(f"  [cyan]superdeploy {self.project_name}:up[/cyan]")
        self.console.print()


@click.command()
@click.argument("target", required=False)
@click.option("--vm-role", help="VM role for infrastructure scaling")
@click.option("--count", type=int, help="Count for VM/app scaling")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def scale(project, target, vm_role, count, verbose, json_output):
    """
    Scale VMs or applications (Heroku-like)

    Updates the project configuration to scale VMs or app replicas.
    After scaling, run 'up' command to apply changes.

    Examples:
        # App scaling (Heroku-like - fast & cheap)
        superdeploy cheapa:scale api=5
        superdeploy cheapa:scale worker=10

        # VM scaling (infrastructure - slow & expensive)
        superdeploy cheapa:scale --vm-role app --count 3
        superdeploy cheapa:scale --vm-role worker --count 2

    Note:
        After scaling, run 'superdeploy <project>:up' to apply changes.
    """
    # Parse target (app=5 format)
    if target and "=" in target:
        app_name, replicas_str = target.split("=", 1)
        try:
            replicas = int(replicas_str)
            options = ScaleOptions("app", app_name, replicas)
        except ValueError:
            raise click.UsageError(f"Invalid replicas count: {replicas_str}")
    elif vm_role and count:
        options = ScaleOptions("vm", vm_role, count)
    else:
        raise click.UsageError(
            "Specify either 'app=N' for app scaling or '--vm-role + --count' for VM scaling\n\n"
            "Examples:\n"
            "  superdeploy cheapa:scale api=5\n"
            "  superdeploy cheapa:scale --vm-role app --count 3"
        )

    cmd = ScaleCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
