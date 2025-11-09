"""SuperDeploy CLI - Status command (Refactored)"""

import click
import json
from rich.table import Table
from cli.base import ProjectCommand


class StatusCommand(ProjectCommand):
    """Show infrastructure and application status."""

    def __init__(self, project_name: str, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.table = Table(
            title=f"{project_name} - Infrastructure Status",
            title_justify="left",
            padding=(0, 1),
        )
        self.table.add_column("Component", style="cyan", no_wrap=True)
        self.table.add_column("Status", style="green")
        self.table.add_column("Details", style="dim")
        self.table.add_column("Version", style="yellow")

    def execute(self) -> None:
        """Execute status command."""
        self.show_header(title="Infrastructure Status", project=self.project_name)

        # Initialize logger
        logger = self.init_logger(self.project_name, "status")

        logger.step("Loading project configuration")

        # Check if deployed
        try:
            self.require_deployment()
            logger.success("Configuration loaded")
        except SystemExit:
            logger.warning("No deployment state found")
            logger.log(f"Run: [red]superdeploy {self.project_name}:up[/red]")
            raise

        logger.step("Checking VM and container status")

        # Get services
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Get all VMs
        all_vms = vm_service.get_all_vms()

        # Get apps
        apps = self.list_apps()

        # Get version info for all apps
        app_versions = {}
        for vm_name in all_vms.keys():
            vm_data = all_vms[vm_name]
            vm_ip = vm_data["external_ip"]

            try:
                result = ssh_service.execute_command(
                    vm_ip,
                    f"cat /opt/superdeploy/projects/{self.project_name}/versions.json 2>/dev/null || echo '[]'",
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout.strip():
                    versions = json.loads(result.stdout)
                    for version in versions:
                        app_name = version["app"]
                        if (
                            app_name not in app_versions
                            or version["deployed_at"]
                            > app_versions[app_name]["deployed_at"]
                        ):
                            app_versions[app_name] = version
            except Exception:
                pass

        # Check each VM and its containers
        for vm_name in sorted(all_vms.keys()):
            vm_data = all_vms[vm_name]
            vm_ip = vm_data["external_ip"]
            role = vm_service.get_vm_role_from_name(vm_name)

            # Test SSH connectivity
            if ssh_service.test_connection(vm_ip):
                vm_status = "[green]Running[/green]"

                # Get container status
                try:
                    result = ssh_service.execute_command(
                        vm_ip,
                        f"docker ps --filter name={self.project_name}- --format '{{{{.Names}}}}\\t{{{{.Status}}}}'",
                        timeout=5,
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        # Add VM header
                        self.table.add_row(
                            f"[bold]{vm_name}[/bold] ({role})", vm_status, vm_ip
                        )

                        # Add containers under this VM
                        for line in result.stdout.strip().split("\n"):
                            if "\t" in line:
                                container, status = line.split("\t", 1)
                                # Extract app name from container name
                                app_name = container.replace(
                                    f"{self.project_name}-", ""
                                )

                                # Add version if available
                                if app_name in app_versions:
                                    version_info = app_versions[app_name]
                                    self.table.add_row(
                                        f"  └─ {app_name}",
                                        status,
                                        "container",
                                        f"{version_info['short_sha']} ({version_info['branch']})",
                                    )
                                else:
                                    self.table.add_row(
                                        f"  └─ {app_name}",
                                        status,
                                        "container",
                                        "-",
                                    )
                    else:
                        # VM running but no containers
                        self.table.add_row(
                            f"[bold]{vm_name}[/bold] ({role})", vm_status, vm_ip
                        )
                        self.table.add_row(
                            "  └─ No containers", "[yellow]Empty[/yellow]", ""
                        )
                except Exception as e:
                    # SSH works but docker command failed
                    self.table.add_row(
                        f"[bold]{vm_name}[/bold] ({role})", vm_status, vm_ip
                    )
                    self.table.add_row("  └─ Error", "[red]Failed[/red]", str(e)[:30])
            else:
                # VM not reachable
                self.table.add_row(
                    f"[bold]{vm_name}[/bold] ({role})", "[red]Unreachable[/red]", vm_ip
                )

        logger.success("Status check complete")

        # Display table
        if not self.verbose:
            self.console.print("\n")
            self.console.print(self.table)
            self.console.print()

            # Show useful commands
            self.console.print("[bold]Useful commands:[/bold]")
            self.console.print("  [cyan]superdeploy logs -a <app> -f[/cyan]")
            self.console.print("  [cyan]superdeploy restart -a <app>[/cyan]")
            self.console.print("  [cyan]superdeploy run <app> <command>[/cyan]")
            self.console.print()

        if not self.verbose:
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def status(project, verbose):
    """
    Show infrastructure and application status

    Displays:
    - VM status per role
    - Container status per VM
    - Application health
    - Deployed versions (Git SHA)
    """
    cmd = StatusCommand(project, verbose=verbose)
    cmd.run()
