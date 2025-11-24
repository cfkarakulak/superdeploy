"""
Down Command

Destroy project resources and clean up infrastructure.
"""

import click
import subprocess
import time
import shutil
from pathlib import Path
from dataclasses import dataclass

from cli.base import ProjectCommand


@dataclass
class DownOptions:
    """Options for down command."""

    yes: bool = False
    keep_infra: bool = False


@dataclass
class CleanupStats:
    """Statistics for cleanup operations."""

    vms_deleted: int = 0
    ips_deleted: int = 0
    firewalls_deleted: int = 0
    subnets_deleted: int = 0
    networks_deleted: int = 0

    def has_resources(self) -> bool:
        """Check if any resources were deleted."""
        return any(
            [
                self.vms_deleted,
                self.ips_deleted,
                self.firewalls_deleted,
                self.subnets_deleted,
                self.networks_deleted,
            ]
        )

    def summary(self) -> str:
        """Get summary string of deleted resources."""
        resources = []
        if self.vms_deleted > 0:
            resources.append(f"{self.vms_deleted} VM(s)")
        if self.firewalls_deleted > 0:
            resources.append(f"{self.firewalls_deleted} firewall rule(s)")
        if self.subnets_deleted > 0:
            resources.append(f"{self.subnets_deleted} subnet(s)")
        if self.networks_deleted > 0:
            resources.append(f"{self.networks_deleted} network(s)")
        if self.ips_deleted > 0:
            resources.append(f"{self.ips_deleted} IP(s)")
        return ", ".join(resources) if resources else "None"


class GCPResourceCleaner:
    """Cleans up GCP resources for a project."""

    def __init__(self, project_name: str, console):
        """
        Initialize GCP resource cleaner.

        Args:
            project_name: Name of the project
            console: Rich console for output
        """
        self.project_name = project_name
        self.console = console

    def cleanup(self, region: str) -> CleanupStats:
        """
        Clean up all GCP resources.

        Args:
            region: GCP region

        Returns:
            CleanupStats with deletion counts
        """
        stats = CleanupStats()

        stats.vms_deleted = self._delete_vms()
        if stats.vms_deleted > 0:
            time.sleep(3)  # Wait for VMs to be deleted

        stats.ips_deleted = self._delete_static_ips(region)
        stats.firewalls_deleted = self._delete_firewall_rules()
        stats.subnets_deleted = self._delete_subnets()
        stats.networks_deleted = self._delete_network()

        return stats

    def _delete_vms(self) -> int:
        """Delete all VMs for this project."""
        vms_deleted = 0
        cmd = (
            f"gcloud compute instances list "
            f"--filter='name~^{self.project_name}-' "
            f"--format='value(name,zone)' 2>/dev/null"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        vm_name, vm_zone = parts[0], parts[1]
                        delete_cmd = (
                            f"gcloud compute instances delete {vm_name} "
                            f"--zone={vm_zone} --quiet"
                        )
                        result = subprocess.run(
                            delete_cmd,
                            shell=True,
                            capture_output=True,
                        )
                        if result.returncode == 0:
                            vms_deleted += 1

        return vms_deleted

    def _delete_static_ips(self, region: str) -> int:
        """Delete all static IPs for this project."""
        ips_deleted = 0
        cmd = (
            f"gcloud compute addresses list "
            f"--filter='name~^{self.project_name}-' "
            f"--format='value(name,region)' 2>/dev/null"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_name, ip_region = parts[0], parts[1]
                        delete_cmd = (
                            f"gcloud compute addresses delete {ip_name} "
                            f"--region={ip_region} --quiet"
                        )
                        result = subprocess.run(
                            delete_cmd,
                            shell=True,
                            capture_output=True,
                        )
                        if result.returncode == 0:
                            ips_deleted += 1

        return ips_deleted

    def _delete_firewall_rules(self) -> int:
        """Delete all firewall rules for this project."""
        firewalls_deleted = 0
        cmd = (
            f"gcloud compute firewall-rules list "
            f"--filter='network~{self.project_name}-network' "
            f"--format='value(name)' 2>/dev/null"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            firewall_rules = result.stdout.strip().split("\n")
            for fw_name in firewall_rules:
                fw_name = fw_name.strip()
                if fw_name:
                    delete_cmd = (
                        f"gcloud compute firewall-rules delete {fw_name} --quiet"
                    )
                    result = subprocess.run(
                        delete_cmd,
                        shell=True,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        firewalls_deleted += 1

        return firewalls_deleted

    def _delete_subnets(self) -> int:
        """Delete all subnets for this project."""
        subnets_deleted = 0
        cmd = (
            f"gcloud compute networks subnets list "
            f"--filter='network~{self.project_name}-network' "
            f"--format='value(name,region)' 2>/dev/null"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        subnet_name, subnet_region = parts[0], parts[1]
                        delete_cmd = (
                            f"gcloud compute networks subnets delete {subnet_name} "
                            f"--region={subnet_region} --quiet"
                        )
                        result = subprocess.run(
                            delete_cmd,
                            shell=True,
                            capture_output=True,
                        )
                        if result.returncode == 0:
                            subnets_deleted += 1

        return subnets_deleted

    def _delete_network(self) -> int:
        """Delete network for this project."""
        network_name = f"{self.project_name}-network"
        result = subprocess.run(
            f"gcloud compute networks delete {network_name} --quiet 2>&1",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            return 1
        return 0


class TerraformCleaner:
    """Cleans up Terraform state and workspaces."""

    def __init__(
        self, project_name: str, project_root: Path, console, project_config=None
    ):
        """
        Initialize Terraform cleaner.

        Args:
            project_name: Name of the project
            project_root: Path to project root
            console: Rich console for output
            project_config: Optional ProjectConfig instance (for terraform destroy)
        """
        self.project_name = project_name
        self.project_root = project_root
        self.console = console
        self.terraform_dir = project_root / "shared" / "terraform"
        self.project_config = project_config

    def cleanup(self) -> None:
        """Clean up Terraform state files and destroy resources."""
        from cli.terraform_utils import TerraformManager

        manager = TerraformManager(self.project_root)

        # Check if workspace exists
        try:
            workspaces = manager.list_workspaces()
            workspace_exists = self.project_name in workspaces
        except Exception:
            # Terraform might not be initialized, that's okay
            workspace_exists = False

        if workspace_exists:
            # Initialize Terraform if needed
            try:
                manager.init(upgrade=False, migrate_state=False)
            except Exception:
                # Init might fail if already initialized, that's okay
                pass

            # Select workspace
            try:
                manager.select_workspace(self.project_name, create=False)

                # Try to destroy Terraform-managed resources first
                if self.project_config:
                    try:
                        self.console.print("  [dim]Running terraform destroy...[/dim]")
                        result = manager.destroy(self.project_config, auto_approve=True)
                        if result.is_success:
                            self.console.print(
                                "  [dim]✓ Terraform resources destroyed[/dim]"
                            )
                        else:
                            # If destroy fails, continue anyway (resources might already be deleted)
                            error_msg = (
                                result.stderr[:200]
                                if result.stderr
                                else "Unknown error"
                            )
                            self.console.print(
                                f"  [yellow]⚠ Terraform destroy had issues: {error_msg}[/yellow]"
                            )
                    except Exception as e:
                        # If destroy fails, continue anyway
                        self.console.print(
                            f"  [yellow]⚠ Could not run terraform destroy: {e}[/yellow]"
                        )
                        self.console.print("  [dim]Continuing with cleanup...[/dim]")
                else:
                    self.console.print(
                        "  [yellow]⚠ No project config available, skipping terraform destroy[/yellow]"
                    )
            except Exception as e:
                self.console.print(
                    f"  [yellow]⚠ Could not select workspace: {e}[/yellow]"
                )

        # Switch to default workspace
        try:
            manager.select_workspace("default", create=False)
        except Exception:
            # Default workspace might not exist, that's okay
            pass

        # Remove workspace directory
        workspace_dir = self.terraform_dir / "terraform.tfstate.d" / self.project_name
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
            self.console.print("  [dim]✓ Terraform workspace cleaned[/dim]")
        elif not workspace_exists:
            self.console.print("  [dim]✓ No Terraform workspace found[/dim]")


class LocalFilesCleaner:
    """Cleans up local project files."""

    def __init__(self, project_name: str, project_root: Path, console, logger):
        """
        Initialize local files cleaner.

        Args:
            project_name: Name of the project
            project_root: Path to project root
            console: Rich console for output
            logger: Logger instance
        """
        self.project_name = project_name
        self.project_root = project_root
        self.console = console
        self.logger = logger

    def cleanup(self) -> None:
        """Clean up local project files."""
        # Delete state.yml
        state_file = self.project_root / "projects" / self.project_name / "state.yml"
        if state_file.exists():
            state_file.unlink()

        # Clean inventory file
        inventory_file = (
            self.project_root
            / "shared"
            / "ansible"
            / "inventories"
            / f"{self.project_name}.ini"
        )
        if inventory_file.exists():
            inventory_file.unlink()

        # Release subnet allocation
        try:
            from cli.subnet_allocator import SubnetAllocator

            allocator = SubnetAllocator()
            allocator.release_subnet(self.project_name)
        except Exception as e:
            self.logger.warning(f"Subnet release warning: {e}")

        self.console.print("  [dim]✓ Local files cleaned[/dim]")


class DownCommand(ProjectCommand):
    """
    Destroy project resources.

    Features:
    - GCP resource cleanup
    - Terraform state cleanup
    - Local files cleanup
    - Confirmation prompt
    """

    def __init__(
        self,
        project_name: str,
        options: DownOptions,
        verbose: bool = False,
        json_output: bool = False,
    ):
        """
        Initialize down command.

        Args:
            project_name: Name of the project
            options: DownOptions with configuration
            verbose: Whether to show verbose output
            json_output: Whether to output in JSON format
        """
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.options = options

    def execute(self) -> None:
        """Execute down command."""
        self.show_header(
            title="Project Shutdown",
            subtitle="[bold red]This will stop all services and destroy all VMs![/bold red]",
            project=self.project_name,
            border_color="red",
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, "down")

        # Show what will be destroyed
        self._show_resources_to_destroy()
        self.console.print()

        # Confirm destruction
        if not self.options.yes and not self._confirm_destruction():
            self.print_warning("❌ Destruction cancelled")
            raise SystemExit(0)

        self.console.print()

        # Load config for GCP details and Terraform
        region = self._load_region_config(logger)
        project_config = self._load_project_config(logger)

        # Execute cleanup in 4 steps
        total_steps = 4

        # Step 1: Terraform Destroy (destroy Terraform-managed resources first)
        if logger:
            logger.step(f"[1/{total_steps}] Terraform Destroy")
        self.console.print("  [dim]✓ Configuration loaded[/dim]")
        self._execute_terraform_cleanup(logger, project_config)

        # Step 2: GCP Resource Cleanup (clean up any remaining resources)
        if logger:
            logger.step(f"[2/{total_steps}] GCP Resource Cleanup")
        self._execute_gcp_cleanup(logger, region)

        # Step 3: Local Files Cleanup
        if logger:
            logger.step(f"[3/{total_steps}] Local Files Cleanup")
        self._execute_local_cleanup(logger)

        # Step 4: Database Cleanup
        if logger:
            logger.step(f"[4/{total_steps}] Database Cleanup")
        self._execute_database_cleanup(logger)

        if not self.verbose:
            self.console.print("\n[color(248)]Project destroyed.[/color(248)]")

    def _load_region_config(self, logger) -> str:
        """Load GCP region from config."""
        try:
            project_config = self.config_service.get_raw_config(self.project_name)
            gcp_config = project_config.get("cloud", {}).get("gcp", {})
            region = gcp_config.get("region", "us-central1")
            if logger:
                logger.log("[dim]✓ Config loaded[/dim]")
            return region
        except Exception:
            if logger:
                logger.log("[dim]No config found, using defaults for cleanup[/dim]")
            return "us-central1"

    def _load_project_config(self, logger):
        """Load ProjectConfig instance for Terraform operations."""
        try:
            from cli.core.config_loader import ConfigLoader

            loader = ConfigLoader(self.project_root)
            return loader.load_project(self.project_name)
        except Exception as e:
            if logger:
                logger.log(f"[dim]Could not load ProjectConfig: {e}[/dim]")
            return None

    def _show_resources_to_destroy(self) -> None:
        """Show resources that will be destroyed."""
        if self.verbose:
            return

        self.console.print("Resources to be destroyed:")

        try:
            from cli.terraform_utils import TerraformManager

            manager = TerraformManager(self.project_root)
            manager.select_workspace(self.project_name, create=False)
            outputs = manager.get_outputs(self.project_name)

            vm_names = outputs.get_value("vm_names", {})
            if vm_names:
                self.console.print(f"  {len(vm_names)} VM(s)")
                for key, name in vm_names.items():
                    self.console.print(f"    - {name}")
            else:
                self.console.print("  [dim]No VMs in Terraform state[/dim]")

            if not self.options.keep_infra:
                self.console.print("  VPC Network & Firewall Rules")

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️  Could not read Terraform state: {e}[/yellow]"
            )
            self.console.print("  [dim]Will attempt destruction anyway[/dim]")

    def _confirm_destruction(self) -> bool:
        """Ask for user confirmation."""
        return self.confirm(
            "[bold red]Are you sure you want to destroy all infrastructure?[/bold red]",
            default=False,
        )

    def _execute_gcp_cleanup(self, logger, region: str) -> None:
        """Execute GCP resource cleanup."""
        cleaner = GCPResourceCleaner(self.project_name, self.console)
        stats = cleaner.cleanup(region)

        if stats.has_resources():
            self.console.print(
                f"  [dim]✓ GCP resources cleaned: {stats.summary()}[/dim]"
            )
        else:
            self.console.print("  [dim]✓ No GCP resources found[/dim]")

    def _execute_terraform_cleanup(self, logger, project_config=None) -> None:
        """Execute Terraform state cleanup."""
        cleaner = TerraformCleaner(
            self.project_name, self.project_root, self.console, project_config
        )
        cleaner.cleanup()

    def _execute_local_cleanup(self, logger) -> None:
        """Execute local files cleanup."""
        cleaner = LocalFilesCleaner(
            self.project_name, self.project_root, self.console, logger
        )
        cleaner.cleanup()

    def _execute_database_cleanup(self, logger) -> None:
        """Execute database cleanup - VMs config is preserved as part of project configuration."""
        # NOTE: VMs configuration is part of the project definition and should NOT be deleted
        # on teardown. It will be reused on next 'up' command.
        # Only runtime state (Terraform state, GCP resources, local files) is cleaned.

        # Clear actual_state JSON to reflect that infrastructure is down
        from cli.sync import clear_actual_state

        clear_actual_state(self.project_name)

        if logger:
            logger.log("[dim]✓ Database preserved (VMs config retained)[/dim]")
        self.console.print("  [dim]✓ Database preserved (VMs config retained)[/dim]")


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option(
    "--keep-infra",
    is_flag=True,
    help="Keep shared infrastructure (only stop project services)",
)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def down(project, yes, verbose, keep_infra, json_output):
    """
    Stop and destroy project resources (like 'heroku apps:destroy')

    This command will:
    - Delete all VMs (core, scrape, proxy)
    - Optionally delete VPC network and firewall rules
    - Clean up local state

    Warning: All data on VMs will be lost.

    Examples:
        # Destroy project with confirmation
        superdeploy cheapa:down

        # Skip confirmation prompt
        superdeploy cheapa:down --yes

        # Keep shared infrastructure
        superdeploy cheapa:down --keep-infra
    """
    options = DownOptions(yes=yes, keep_infra=keep_infra)
    cmd = DownCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
