"""SuperDeploy CLI - Scale command (Refactored)"""

import click
from cli.base import ProjectCommand


class ScaleCommand(ProjectCommand):
    """Scale VM count for a role."""

    def __init__(
        self, project_name: str, vm_role: str, count: int, verbose: bool = False
    ):
        super().__init__(project_name, verbose=verbose)
        self.vm_role = vm_role
        self.count = count

    def execute(self) -> None:
        """Execute scale command."""
        self.show_header(
            title="Scale Infrastructure",
            project=self.project_name,
            details={"VM Role": self.vm_role, "Count": str(self.count)},
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"scale-{self.vm_role}")

        logger.step("Validating Configuration")

        # Get current VM config
        vms_config = self.config_service.get_vms(self.project_name)

        if self.vm_role not in vms_config:
            self.exit_with_error(
                f"VM role '{self.vm_role}' not found in project config\n"
                f"Available roles: {', '.join(vms_config.keys())}"
            )

        current_count = vms_config[self.vm_role].get("count", 1)
        logger.log(f"Current count: {current_count}")
        logger.log(f"Target count: {self.count}")

        if current_count == self.count:
            self.print_warning(
                f"VM role '{self.vm_role}' is already at {self.count} instance(s)"
            )
            return

        # Confirm scaling action
        action = "scale up" if self.count > current_count else "scale down"
        if not self.confirm(
            f"[yellow]{action.title()} {self.vm_role} from {current_count} to {self.count} instance(s)?[/yellow]",
            default=False,
        ):
            self.print_warning("Scaling cancelled")
            return

        logger.step("Updating Configuration")

        # Update project.yml
        try:
            import yaml

            project_path = self.config_service.get_project_path(self.project_name)
            project_yml = project_path / "project.yml"

            with open(project_yml, "r") as f:
                config = yaml.safe_load(f)

            config["vms"][self.vm_role]["count"] = self.count

            with open(project_yml, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            logger.log(f"✓ Updated {project_yml}")

        except Exception as e:
            self.handle_error(e, "Failed to update configuration")
            raise SystemExit(1)

        logger.step("Applying Changes")

        self.console.print("\n[bold yellow]To apply these changes, run:[/bold yellow]")
        self.console.print(f"  [cyan]superdeploy {self.project_name}:up[/cyan]")
        self.console.print()

        logger.success("Configuration updated")

        if not self.verbose:
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")


@click.command()
@click.option("--vm-role", required=True, help="VM role (api, web, worker)")
@click.option("--count", type=int, required=True, help="Number of VMs")
def scale(project, vm_role, count):
    """
    Scale VM count for a role

    \b
    Example:
      superdeploy myproject:scale --vm-role worker --count 3

    \b
    Note: After scaling, run 'superdeploy up' to apply changes.
    """
    cmd = ScaleCommand(project, vm_role, count, verbose=False)
    cmd.run()
