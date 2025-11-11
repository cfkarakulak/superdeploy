"""Orchestrator status command."""

import click
from pathlib import Path
from rich.table import Table

from cli.base import BaseCommand
from cli.core.orchestrator_loader import OrchestratorLoader


class OrchestratorStatusCommand(BaseCommand):
    """Show orchestrator status."""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.table = Table(
            title="Orchestrator - Infrastructure Status",
            title_justify="left",
            padding=(0, 1),
        )
        self.table.add_column("Component", style="cyan", no_wrap=True)
        self.table.add_column("Status", style="green")
        self.table.add_column("Details", style="dim")
        self.table.add_column("Info", style="yellow")

    def execute(self) -> None:
        """Execute status command."""
        self.show_header(title="Orchestrator Status", project="orchestrator")

        # Initialize logger
        logger = self.init_logger("orchestrator", "status")

        project_root = Path.cwd()
        shared_dir = project_root / "shared"

        orchestrator_loader = OrchestratorLoader(shared_dir)

        logger.step("Loading orchestrator configuration")

        try:
            orch_config = orchestrator_loader.load()
        except FileNotFoundError as e:
            logger.log_error(f"Configuration not found: {e}")
            self.console.print(f"[red]❌ {e}[/red]")
            raise SystemExit(1)

        if orch_config.is_deployed():
            logger.success("Configuration loaded")
            self._display_deployed_status(orch_config, logger)
        else:
            self._display_not_deployed(logger)

        if not self.verbose:
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _display_deployed_status(self, orch_config, logger) -> None:
        """Display status for deployed orchestrator."""
        logger.step("Checking orchestrator VM and containers")

        # Get orchestrator details
        orch_ip = orch_config.get_ip()
        state = orch_config.state_manager.load_state()
        last_updated = state.get("last_updated", "Unknown")
        vm_info = state.get("vm", {})

        # Add VM info to table
        self.table.add_row(
            "[bold]Orchestrator VM[/bold]",
            "[green]Deployed[/green]",
            orch_ip,
            vm_info.get("machine_type", "-"),
        )

        # Test SSH connectivity
        from cli.services.ssh_service import SSHService

        ssh_service = SSHService()

        if ssh_service.test_connection(orch_ip):
            logger.success("SSH connection successful")

            # Get container status
            try:
                result = ssh_service.execute_command(
                    orch_ip,
                    "docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E '^superdeploy-|^portainer|^caddy'",
                    timeout=10,
                )

                if self.verbose:
                    logger.log(f"Containers on orchestrator: {result.stdout.strip()}")

                if result.returncode == 0 and result.stdout.strip():
                    # Parse and display containers
                    containers = result.stdout.strip().split("\n")
                    logger.success(f"Found {len(containers)} running containers")

                    for line in containers:
                        if "\t" in line:
                            parts = line.split("\t")
                            container_name = parts[0]
                            status = parts[1] if len(parts) > 1 else "-"
                            ports = parts[2] if len(parts) > 2 else "-"

                            # Clean up container name for display
                            display_name = container_name
                            if container_name.startswith("superdeploy-"):
                                display_name = container_name.replace(
                                    "superdeploy-", "", 1
                                )

                            # Extract port info if available
                            port_info = "-"
                            if ports and ports != "-":
                                # Extract just the main port numbers
                                if ":" in ports:
                                    port_parts = ports.split("->")
                                    if len(port_parts) > 1:
                                        port_info = port_parts[1].split("/")[0]

                            self.table.add_row(
                                f"  └─ {display_name}", status, "container", port_info
                            )
                else:
                    logger.warning("No containers found")
                    self.table.add_row(
                        "  └─ No containers", "[yellow]Empty[/yellow]", "", ""
                    )

                # Check disk usage
                disk_result = ssh_service.execute_command(
                    orch_ip,
                    'df -h / | tail -n 1 | awk \'{print $5 " (" $4 " free)"}\'',
                    timeout=5,
                )

                if disk_result.returncode == 0 and disk_result.stdout.strip():
                    disk_usage = disk_result.stdout.strip()
                    self.table.add_row(
                        "[bold]Disk Usage[/bold]",
                        "",
                        disk_usage,
                        f"{vm_info.get('disk_size', '-')}GB",
                    )

                # Check memory usage
                mem_result = ssh_service.execute_command(
                    orch_ip,
                    "free -h | grep Mem | awk '{print $3 \"/\" $2}'",
                    timeout=5,
                )

                if mem_result.returncode == 0 and mem_result.stdout.strip():
                    mem_usage = mem_result.stdout.strip()
                    self.table.add_row("[bold]Memory Usage[/bold]", "", mem_usage, "")

            except Exception as e:
                logger.log_error(f"Error checking containers: {e}")
                self.table.add_row("  └─ Error", "[red]Failed[/red]", str(e)[:40], "")
        else:
            logger.warning("SSH connection failed")
            self.table.add_row(
                "[bold]SSH Connection[/bold]", "[red]Unreachable[/red]", orch_ip, ""
            )

        # Add metadata
        self.table.add_row("[bold]Last Updated[/bold]", "", last_updated, "")

        logger.success("Status check complete")

        # Display table
        if not self.verbose:
            self.console.print("\n")
            self.console.print(self.table)
            self.console.print()

            # Show useful info
            self.console.print("[bold]Access URLs:[/bold]")
            self.console.print(f"  [cyan]Portainer: http://{orch_ip}:9000[/cyan]")
            self.console.print(f"  [cyan]Orchestrator: http://{orch_ip}:3001[/cyan]")
            self.console.print()

            self.console.print("[bold]Useful commands:[/bold]")
            self.console.print("  [cyan]superdeploy orchestrator:down[/cyan]")
            self.console.print("  [cyan]superdeploy tunnel orchestrator[/cyan]")
            self.console.print()

    def _display_not_deployed(self, logger) -> None:
        """Display status for non-deployed orchestrator."""
        logger.warning("Orchestrator not deployed")
        self.console.print("[yellow]⚠️  Orchestrator not deployed[/yellow]")
        self.console.print("  Run: [red]superdeploy orchestrator:up[/red]")


@click.command(name="orchestrator:status")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def orchestrator_status(verbose):
    """
    Show orchestrator infrastructure and container status

    Displays:
    - VM status and connectivity
    - Container status (Portainer, Caddy, etc.)
    - Resource usage (disk, memory)
    - Access URLs and useful commands
    """
    cmd = OrchestratorStatusCommand(verbose=verbose)
    cmd.run()
