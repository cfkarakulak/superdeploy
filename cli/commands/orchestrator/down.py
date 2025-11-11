"""Orchestrator shutdown command."""

import click
import subprocess
import shutil
from pathlib import Path

from cli.base import BaseCommand
from cli.core.orchestrator_loader import OrchestratorLoader
from cli.terraform_utils import workspace_exists
from cli.subnet_allocator import SubnetAllocator


class OrchestratorDownCommand(BaseCommand):
    """Destroy orchestrator VM and clean up state."""

    def __init__(
        self, yes: bool = False, preserve_ip: bool = False, verbose: bool = False
    ):
        super().__init__(verbose=verbose)
        self.yes = yes
        self.preserve_ip = preserve_ip

    def execute(self) -> None:
        """Execute down command."""
        self.show_header(
            title="Orchestrator Shutdown",
            subtitle="[bold red]This will destroy the orchestrator VM and clean up all state![/bold red]",
            project="orchestrator",
            border_color="red",
        )

        # Initialize logger
        logger = self.init_logger("orchestrator", "down")

        project_root = Path.cwd()
        shared_dir = project_root / "shared"

        # Show what will be destroyed
        if not self.verbose:
            self._show_resources_to_destroy()
            self.console.print()

        # Confirm destruction
        if not self._confirm_destruction(logger):
            return

        self.console.print()

        # Load config
        zone, region = self._load_config(shared_dir, logger)

        # Execute cleanup
        self._execute_cleanup(logger, project_root, shared_dir, zone, region)

        if not self.verbose:
            self.console.print("\n[color(248)]Orchestrator destroyed.[/color(248)]")
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _show_resources_to_destroy(self) -> None:
        """Show orchestrator resources that will be destroyed."""
        if self.verbose:
            return

        self.console.print("Resources to be destroyed:")

        # Check for VMs
        result = subprocess.run(
            "gcloud compute instances list --filter='name:orchestrator-*' --format='value(name)' 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
        )

        vm_names = []
        if result.returncode == 0 and result.stdout.strip():
            vm_names = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]

        if vm_names:
            self.console.print(f"  {len(vm_names)} VM(s)")
            for name in vm_names:
                self.console.print(f"    - {name}")
        else:
            self.console.print("  [dim]No VMs found[/dim]")

        # Check for Static IP (if not preserving)
        if not self.preserve_ip:
            result = subprocess.run(
                "gcloud compute addresses list --filter='name:orchestrator-*' --format='value(name)' 2>/dev/null",
                shell=True,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                self.console.print("  Static IP")

        # Always show network resources
        self.console.print("  VPC Network & Firewall Rules")

    def _confirm_destruction(self, logger) -> bool:
        """Confirm orchestrator destruction."""
        if self.yes:
            return True

        self.console.print(
            "[bold red]Are you sure you want to destroy the orchestrator?[/bold red] "
            "[bold bright_white]\\[y/n][/bold bright_white] [dim](n)[/dim]: ",
            end="",
        )
        answer = input().strip().lower()
        confirmed = answer in ["y", "yes"]

        if not confirmed:
            self.console.print("[yellow]❌ Destruction cancelled[/yellow]")
            logger.log("User cancelled destruction")

        return confirmed

    def _load_config(self, shared_dir: Path, logger) -> tuple[str, str]:
        """Load orchestrator config and return zone, region."""
        orchestrator_loader = OrchestratorLoader(shared_dir)

        try:
            orch_config = orchestrator_loader.load()
            gcp_config = orch_config.config.get("gcp", {})
            zone = gcp_config.get("zone", "us-central1-a")
            region = gcp_config.get("region", "us-central1")
        except FileNotFoundError:
            logger.log("[dim]No config found, using defaults for cleanup[/dim]")
            zone = "us-central1-a"
            region = "us-central1"

        return zone, region

    def _execute_cleanup(
        self, logger, project_root: Path, shared_dir: Path, zone: str, region: str
    ) -> None:
        """Execute all cleanup steps."""
        # Step 1: GCP Resource Cleanup
        self._cleanup_gcp_resources(logger, zone, region)

        # Step 2: Terraform State Cleanup
        self._cleanup_terraform_state(logger, shared_dir)

        # Step 3: Local Files Cleanup
        self._cleanup_local_files(logger, shared_dir)

    def _cleanup_gcp_resources(self, logger, zone: str, region: str) -> None:
        """Clean up GCP resources."""
        logger.step("[1/3] GCP Resource Cleanup")
        self.console.print("  [dim]✓ Configuration loaded[/dim]")

        vms_deleted = 0
        ips_deleted = 0
        firewalls_deleted = 0
        subnets_deleted = 0
        networks_deleted = 0

        # Delete VM instances first
        result = subprocess.run(
            "gcloud compute instances list --filter='name:orchestrator-*' --format='value(name,zone)' 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        vm_name, vm_zone = parts[0], parts[1]
                        result = subprocess.run(
                            f"gcloud compute instances delete {vm_name} --zone={vm_zone} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        if result.returncode == 0:
                            vms_deleted += 1

        # Delete External IP (unless --preserve-ip flag is set)
        if not self.preserve_ip:
            result = subprocess.run(
                "gcloud compute addresses list --filter='name:orchestrator-*' --format='value(name,region)' 2>/dev/null",
                shell=True,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            ip_name, ip_region = parts[0], parts[1]
                            result = subprocess.run(
                                f"gcloud compute addresses delete {ip_name} --region={ip_region} --quiet",
                                shell=True,
                                capture_output=True,
                            )
                            if result.returncode == 0:
                                ips_deleted += 1

        # Delete Firewall Rules
        result = subprocess.run(
            "gcloud compute firewall-rules list --filter='network:superdeploy-network' --format='value(name)' 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            firewall_rules = result.stdout.strip().split("\n")
            for rule in firewall_rules:
                rule = rule.strip()
                if rule:
                    result = subprocess.run(
                        f"gcloud compute firewall-rules delete {rule} --quiet",
                        shell=True,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        firewalls_deleted += 1

        # Delete Subnet
        result = subprocess.run(
            f"gcloud compute networks subnets delete superdeploy-network-subnet --region={region} --quiet 2>&1",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            subnets_deleted += 1

        # Delete Network
        result = subprocess.run(
            "gcloud compute networks delete superdeploy-network --quiet 2>&1",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            networks_deleted += 1

        # Show summary
        resources = []
        if vms_deleted > 0:
            resources.append(f"{vms_deleted} VM(s)")
        if firewalls_deleted > 0:
            resources.append(f"{firewalls_deleted} firewall rule(s)")
        if subnets_deleted > 0:
            resources.append(f"{subnets_deleted} subnet(s)")
        if networks_deleted > 0:
            resources.append(f"{networks_deleted} network(s)")
        if ips_deleted > 0:
            resources.append(f"{ips_deleted} IP(s)")

        if resources:
            self.console.print(
                f"  [dim]✓ GCP resources cleaned: {', '.join(resources)}[/dim]"
            )
        else:
            self.console.print("  [dim]✓ No GCP resources found[/dim]")

    def _cleanup_terraform_state(self, logger, shared_dir: Path) -> None:
        """Clean up Terraform state."""
        logger.step("[2/3] Terraform State Cleanup")

        terraform_dir = shared_dir / "terraform"
        workspace_found = workspace_exists("orchestrator")

        if workspace_found:
            # Switch to default workspace
            subprocess.run(
                "terraform workspace select default 2>/dev/null || true",
                shell=True,
                cwd=terraform_dir,
                capture_output=True,
            )

            # Remove the workspace directory
            terraform_state_dir = terraform_dir / "terraform.tfstate.d" / "orchestrator"
            if terraform_state_dir.exists():
                shutil.rmtree(terraform_state_dir)
                self.console.print("  [dim]✓ Terraform workspace cleaned[/dim]")
        else:
            self.console.print("  [dim]✓ No Terraform workspace found[/dim]")

    def _cleanup_local_files(self, logger, shared_dir: Path) -> None:
        """Clean up local files."""
        logger.step("[3/3] Local Files Cleanup")

        # Delete state.yml
        state_file = shared_dir / "orchestrator" / "state.yml"
        if state_file.exists():
            state_file.unlink()

        # Clean inventory
        inventory_file = shared_dir / "ansible" / "inventories" / "orchestrator.ini"
        if inventory_file.exists():
            inventory_file.unlink()

        # Release subnet allocation
        try:
            allocator = SubnetAllocator()
            allocator.release_subnet("orchestrator")
        except Exception as e:
            logger.warning(f"Subnet release warning: {e}")

        self.console.print("  [dim]✓ Local files cleaned[/dim]")


@click.command(name="orchestrator:down")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--preserve-ip", is_flag=True, help="Keep static IP (don't delete)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def orchestrator_down(yes, preserve_ip, verbose):
    """Destroy orchestrator VM and clean up state"""
    cmd = OrchestratorDownCommand(yes=yes, preserve_ip=preserve_ip, verbose=verbose)
    cmd.run()
