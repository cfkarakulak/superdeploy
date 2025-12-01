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
        self,
        yes: bool = False,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.yes = yes

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

        # Static IP will be destroyed
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
        self.console.print()  # Add newline after user input
        confirmed = answer in ["y", "yes"]

        if not confirmed:
            self.console.print("[yellow]❌ Destruction cancelled[/yellow]")
            if logger:
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
            if logger:
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

        # Step 4: Database Cleanup
        self._cleanup_database(logger)

    def _cleanup_gcp_resources(self, logger, zone: str, region: str) -> None:
        """Clean up GCP resources using Terraform destroy, then hard cleanup."""
        if logger:
            logger.step("[1/4] GCP Resource Cleanup")
        self.console.print("  [dim]✓ Configuration loaded[/dim]")

        # Use Terraform destroy - this properly removes all resources including network
        from cli.terraform_utils import select_workspace

        project_root = Path.cwd()
        terraform_dir = project_root / "shared" / "terraform"
        terraform_success = False

        try:
            # Select orchestrator workspace (create=True to avoid failure if doesn't exist)
            select_workspace("orchestrator", create=True)

            if logger:
                logger.log("Running Terraform destroy...")

            # Run Terraform destroy with longer timeout for network resources
            result = subprocess.run(
                "terraform destroy -auto-approve -no-color -compact-warnings",
                shell=True,
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for network cleanup
            )

            if result.returncode == 0:
                if logger:
                    logger.log("✓ All GCP resources destroyed via Terraform")
                self.console.print(
                    "  [dim]✓ Infrastructure destroyed (Terraform)[/dim]"
                )
                terraform_success = True
            else:
                if logger:
                    logger.warning(
                        f"Terraform destroy returned non-zero: {result.returncode}"
                    )
                if self.verbose:
                    self.console.print(f"[yellow]{result.stderr}[/yellow]")
        except subprocess.TimeoutExpired:
            if logger:
                logger.warning("Terraform destroy timed out")
        except Exception as e:
            if logger:
                logger.warning(f"Terraform destroy failed: {e}")

        # ALWAYS run hard cleanup to ensure nothing is left behind
        # Even if Terraform succeeded, verify with gcloud
        if logger:
            logger.log("Running hard cleanup verification...")

        # Fallback: Manual cleanup (legacy)
        if logger:
            logger.log("Using manual GCP resource cleanup...")

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
                            f"gcloud compute instances delete {vm_name} --zone={vm_zone} --quiet 2>&1",
                            shell=True,
                            capture_output=True,
                            text=True,
                        )
                        if (
                            result.returncode == 0
                            or "not found" in result.stderr.lower()
                        ):
                            if "not found" not in result.stderr.lower():
                                vms_deleted += 1

        # Wait for VMs to terminate
        if vms_deleted > 0:
            import time

            time.sleep(5)

        # Delete External IP (always delete)
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
                            f"gcloud compute addresses delete {ip_name} --region={ip_region} --quiet 2>&1",
                            shell=True,
                            capture_output=True,
                            text=True,
                        )
                        if (
                            result.returncode == 0
                            or "not found" in result.stderr.lower()
                        ):
                            if "not found" not in result.stderr.lower():
                                ips_deleted += 1

        # Delete Firewall Rules - HARD RESET
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
                        f"gcloud compute firewall-rules delete {rule} --quiet 2>&1",
                        shell=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0 or "not found" in result.stderr.lower():
                        if "not found" not in result.stderr.lower():
                            firewalls_deleted += 1

        # Wait for firewall rules to be deleted
        import time

        time.sleep(2)

        # Delete VPC Peerings first (they block network deletion)
        peerings_deleted = 0
        result = subprocess.run(
            "gcloud compute networks peerings list --network=superdeploy-network --format='value(name)' 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            peerings = result.stdout.strip().split("\n")
            for peering in peerings:
                peering = peering.strip()
                if peering:
                    subprocess.run(
                        f"gcloud compute networks peerings delete {peering} --network=superdeploy-network --quiet 2>&1",
                        shell=True,
                        capture_output=True,
                        text=True,
                    )
                    peerings_deleted += 1

        if peerings_deleted > 0:
            time.sleep(2)

        # Delete Subnet - HARD RESET
        result = subprocess.run(
            f"gcloud compute networks subnets delete superdeploy-network-subnet --region={region} --quiet 2>&1",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            if "not found" not in result.stderr.lower():
                subnets_deleted += 1

        # Wait for subnet to be deleted
        time.sleep(2)

        # Delete Network - HARD RESET with retries
        for attempt in range(3):
            result = subprocess.run(
                "gcloud compute networks delete superdeploy-network --quiet 2>&1",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                networks_deleted += 1
                break
            elif "not found" in result.stderr.lower():
                break
            elif "in use" in result.stderr.lower() and attempt < 2:
                time.sleep(3)
                continue

        # Show summary
        resources = []
        if vms_deleted > 0:
            resources.append(f"{vms_deleted} VM(s)")
        if firewalls_deleted > 0:
            resources.append(f"{firewalls_deleted} firewall rule(s)")
        if peerings_deleted > 0:
            resources.append(f"{peerings_deleted} VPC peering(s)")
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
        """Clean up Terraform state - HARD RESET."""
        if logger:
            logger.step("[2/4] Terraform State Cleanup")

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

            # HARD RESET: Force delete workspace
            result = subprocess.run(
                ["terraform", "workspace", "delete", "-force", "orchestrator"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.console.print("  [dim]✓ Terraform workspace force deleted[/dim]")
            else:
                self.console.print(
                    "  [yellow]⚠ Workspace delete warning: continuing anyway[/yellow]"
                )

            # Remove the workspace directory
            terraform_state_dir = terraform_dir / "terraform.tfstate.d" / "orchestrator"
            if terraform_state_dir.exists():
                shutil.rmtree(terraform_state_dir)
                self.console.print("  [dim]✓ Terraform state directory removed[/dim]")
        else:
            self.console.print("  [dim]✓ No Terraform workspace found[/dim]")

    def _cleanup_local_files(self, logger, shared_dir: Path) -> None:
        """Clean up local files."""
        if logger:
            logger.step("[3/4] Local Files Cleanup")

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
            if logger:
                logger.warning(f"Subnet release warning: {e}")

        self.console.print("  [dim]✓ Local files cleaned[/dim]")

    def _cleanup_database(self, logger) -> None:
        """Clean up database state for orchestrator."""
        if logger:
            logger.step("[4/4] Database Cleanup")

        from cli.sync import clear_project_state

        clear_project_state("orchestrator")

        if logger:
            logger.log("✓ Database state cleared")
        self.console.print("  [dim]✓ Database state cleared[/dim]")


@click.command(name="orchestrator:down")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def orchestrator_down(yes, verbose, json_output):
    """Destroy orchestrator VM and clean up state"""
    cmd = OrchestratorDownCommand(yes=yes, verbose=verbose, json_output=json_output)
    cmd.run()
