"""Orchestrator initialization command."""

import click
import importlib.util
from pathlib import Path
from dataclasses import dataclass
from rich.prompt import Prompt

from cli.base import BaseCommand


@dataclass
class OrchestratorConfig:
    """Configuration for orchestrator setup."""

    gcp_project: str
    region: str
    zone: str
    ssl_email: str
    docker_subnet: str


class OrchestratorInitCommand(BaseCommand):
    """Initialize orchestrator configuration."""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)

    def execute(self) -> None:
        """Execute init command."""
        self.show_header(
            title="Orchestrator Setup",
            subtitle="Global monitoring (Prometheus + Grafana)",
            project="orchestrator",
            show_logo=True,
        )

        # Initialize logger
        logger = self.init_logger("orchestrator", "init")

        project_root = Path.cwd()
        orchestrator_dir = project_root / "shared" / "orchestrator"
        orchestrator_dir.mkdir(parents=True, exist_ok=True)

        config_path = orchestrator_dir / "config.yml"

        logger.step("Checking existing configuration")

        # Check if config exists
        if not self._confirm_overwrite(config_path, logger):
            return

        logger.step("Collecting configuration")

        # Collect configuration
        config = self._collect_configuration()

        logger.step("Generating configuration file")

        # Generate and save config
        self._generate_config(config, config_path, project_root, logger)

        logger.success("Orchestrator configuration created")

        # Display next steps
        self._display_next_steps()

        if not self.verbose:
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _confirm_overwrite(self, config_path: Path, logger) -> bool:
        """Confirm overwrite if config exists."""
        if config_path.exists():
            logger.warning("Configuration file already exists")
            self.console.print(
                "[yellow]Config exists. Overwrite? [y/n][/yellow] [dim](n)[/dim]: ",
                end="",
            )
            answer = input().strip().lower()
            self.console.print()
            if answer not in ["y", "yes"]:
                logger.log("User cancelled initialization")
                self.console.print("[dim]Cancelled[/dim]")
                return False
        else:
            logger.log("No existing configuration found")
        return True

    def _collect_configuration(self) -> OrchestratorConfig:
        """Collect orchestrator configuration from user."""
        # Cloud Configuration
        self.console.print("\n[white]Cloud Configuration[/white]")
        gcp_project = Prompt.ask("GCP Project ID", default="")
        region = Prompt.ask("GCP Region", default="us-central1")
        zone = Prompt.ask("GCP Zone", default=f"{region}-a")

        # SSL Configuration
        self.console.print("\n[white]SSL Configuration[/white]")
        ssl_email = Prompt.ask("Email for Let's Encrypt", default="")

        # Allocate Docker subnet
        docker_subnet = self._allocate_docker_subnet()

        return OrchestratorConfig(
            gcp_project=gcp_project,
            region=region,
            zone=zone,
            ssl_email=ssl_email,
            docker_subnet=docker_subnet,
        )

    def _allocate_docker_subnet(self) -> str:
        """Allocate Docker subnet for orchestrator."""
        self.console.print("\n[dim]Allocating network subnet...[/dim]")

        from cli.subnet_allocator import SubnetAllocator

        allocator = SubnetAllocator()

        if "orchestrator" not in allocator.docker_allocations:
            docker_subnet = SubnetAllocator.ORCHESTRATOR_DOCKER_SUBNET
            allocator.docker_allocations["orchestrator"] = docker_subnet
            allocator.allocations["docker_subnets"] = allocator.docker_allocations
            allocator._save_allocations()
        else:
            docker_subnet = allocator.docker_allocations["orchestrator"]

        self.console.print(f"[dim]✓ Subnet allocated: {docker_subnet}[/dim]")
        return docker_subnet

    def _generate_config(
        self, config: OrchestratorConfig, config_path: Path, project_root: Path, logger
    ) -> None:
        """Generate and save orchestrator config."""
        logger.log("Generating config.yml...")

        cli_root = Path(__file__).resolve().parents[2]
        stub_file = cli_root / "stubs" / "configs" / "orchestrator_config_generator.py"
        spec = importlib.util.spec_from_file_location(
            "orchestrator_config_generator", stub_file
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore

        config_content = module.generate_orchestrator_config(
            gcp_project=config.gcp_project,
            region=config.region,
            zone=config.zone,
            ssl_email=config.ssl_email,
            docker_subnet=config.docker_subnet,
        )

        with open(config_path, "w") as f:
            f.write(config_content)

        logger.log(f"Config saved: {config_path.relative_to(project_root)}")

    def _display_next_steps(self) -> None:
        """Display next steps after initialization."""
        self.console.print("\n[white]Next steps:[/white]")
        self.console.print("  [dim]1. Review: shared/orchestrator/config.yml[/dim]")
        self.console.print("  [dim]2. Deploy: superdeploy orchestrator:up[/dim]\n")


@click.command(name="orchestrator:init")
def orchestrator_init():
    """Initialize orchestrator configuration"""
    cmd = OrchestratorInitCommand()
    cmd.run()
