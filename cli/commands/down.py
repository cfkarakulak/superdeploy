"""SuperDeploy CLI - Down command (Refactored)"""

import click
import subprocess
import time
from cli.base import ProjectCommand


class DownCommand(ProjectCommand):
    """Destroy project resources."""

    def __init__(
        self,
        project_name: str,
        yes: bool = False,
        keep_infra: bool = False,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.yes = yes
        self.keep_infra = keep_infra

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
        self._show_resources_to_destroy(logger)
        self.console.print()

        # Confirm destruction
        if not self.yes and not self._confirm_destruction():
            self.print_warning("❌ Destruction cancelled")
            raise SystemExit(0)

        self.console.print()

        # Load config for GCP details (using ProjectCommand's config_service)
        try:
            project_config = self.config_service.get_raw_config(self.project_name)
            gcp_config = project_config.get("cloud", {}).get("gcp", {})
            region = gcp_config.get("region", "us-central1")
            logger.log("[dim]✓ Config loaded[/dim]")
        except Exception:
            # Config not found - use defaults for cleanup
            # This is OK for down command since we're destroying everything anyway
            region = "us-central1"
            logger.log("[dim]No config found, using defaults for cleanup[/dim]")

        # Always 3 steps: GCP Cleanup, Terraform State, Local Files
        total_steps = 3

        # Step 1: GCP Resource Cleanup (ALWAYS do this first to ensure resources are deleted)
        logger.step(f"[1/{total_steps}] GCP Resource Cleanup")
        self._gcp_cleanup(logger, region)

        # Step 2: Terraform State Cleanup
        logger.step(f"[2/{total_steps}] Terraform State Cleanup")
        self._terraform_state_cleanup(logger)

        # Step 3: Local Files Cleanup
        logger.step(f"[3/{total_steps}] Local Files Cleanup")
        self._local_files_cleanup(logger)

        if not self.verbose:
            self.console.print("\n[color(248)]Project destroyed.[/color(248)]")

    def _show_resources_to_destroy(self, logger) -> None:
        """Show resources that will be destroyed."""
        if self.verbose:
            return

        self.console.print("Resources to be destroyed:")

        # Try to get resources from Terraform state
        try:
            from cli.terraform_utils import select_workspace, get_terraform_outputs

            select_workspace(self.project_name, create=False)
            outputs = get_terraform_outputs(self.project_name)

            if outputs and "vm_names" in outputs:
                vm_names = outputs["vm_names"].get("value", {})
                if vm_names:
                    self.console.print(f"  {len(vm_names)} VM(s)")
                    for key, name in vm_names.items():
                        self.console.print(f"    - {name}")
                else:
                    self.console.print("  [dim]No VMs in Terraform state[/dim]")
            else:
                self.console.print("  [dim]No VMs in Terraform state[/dim]")

            if not self.keep_infra:
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

    def _gcp_cleanup(self, logger, region: str) -> None:
        """Clean up all GCP resources for this project."""

        self.console.print("  [dim]✓ Starting GCP resource cleanup[/dim]")

        vms_deleted = 0
        ips_deleted = 0
        firewalls_deleted = 0
        subnets_deleted = 0
        networks_deleted = 0

        # Delete all VMs for this project
        vm_list_cmd = f"gcloud compute instances list --filter='name~^{self.project_name}-' --format='value(name,zone)' 2>/dev/null"
        result = subprocess.run(vm_list_cmd, shell=True, capture_output=True, text=True)

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
            # Wait for VMs to be deleted
            if vms_deleted > 0:
                time.sleep(3)

        # Delete all static IPs
        ip_list_cmd = f"gcloud compute addresses list --filter='name~^{self.project_name}-' --format='value(name,region)' 2>/dev/null"
        result = subprocess.run(ip_list_cmd, shell=True, capture_output=True, text=True)

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

        # Delete all firewall rules
        fw_list_cmd = f"gcloud compute firewall-rules list --filter='network~{self.project_name}-network' --format='value(name)' 2>/dev/null"
        result = subprocess.run(fw_list_cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            firewall_rules = result.stdout.strip().split("\n")
            for fw_name in firewall_rules:
                fw_name = fw_name.strip()
                if fw_name:
                    result = subprocess.run(
                        f"gcloud compute firewall-rules delete {fw_name} --quiet",
                        shell=True,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        firewalls_deleted += 1

        # Delete subnets
        subnet_list_cmd = f"gcloud compute networks subnets list --filter='network~{self.project_name}-network' --format='value(name,region)' 2>/dev/null"
        result = subprocess.run(
            subnet_list_cmd, shell=True, capture_output=True, text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        subnet_name, subnet_region = parts[0], parts[1]
                        result = subprocess.run(
                            f"gcloud compute networks subnets delete {subnet_name} --region={subnet_region} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        if result.returncode == 0:
                            subnets_deleted += 1

        # Delete network
        network_name = f"{self.project_name}-network"
        result = subprocess.run(
            f"gcloud compute networks delete {network_name} --quiet 2>&1",
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
        if ips_deleted > 0:
            resources.append(f"{ips_deleted} IP(s)")
        if firewalls_deleted > 0:
            resources.append(f"{firewalls_deleted} firewall(s)")
        if subnets_deleted > 0:
            resources.append(f"{subnets_deleted} subnet(s)")
        if networks_deleted > 0:
            resources.append(f"{networks_deleted} network(s)")

        if resources:
            self.console.print(
                f"  [dim]✓ GCP resources cleaned: {', '.join(resources)}[/dim]"
            )
        else:
            self.console.print("  [dim]✓ No GCP resources found[/dim]")

    def _terraform_state_cleanup(self, logger) -> None:
        """Clean up Terraform state files."""

        terraform_dir = self.project_root / "shared" / "terraform"

        # Switch to default workspace
        subprocess.run(
            "terraform workspace select default 2>/dev/null || true",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
        )

        # Remove workspace directory
        terraform_state_dir = terraform_dir / "terraform.tfstate.d" / self.project_name
        if terraform_state_dir.exists():
            import shutil

            shutil.rmtree(terraform_state_dir)
            self.console.print("  [dim]✓ Terraform workspace cleaned[/dim]")
        else:
            self.console.print("  [dim]✓ No Terraform workspace found[/dim]")

    def _local_files_cleanup(self, logger) -> None:
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
            logger.warning(f"Subnet release warning: {e}")

        self.console.print("  [dim]✓ Local files cleaned[/dim]")


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option(
    "--keep-infra",
    is_flag=True,
    help="Keep shared infrastructure (only stop project services)",
)
def down(project, yes, verbose, keep_infra):
    """
    Stop and destroy project resources (like 'heroku apps:destroy')

    This command will:
    - Delete all VMs (core, scrape, proxy)
    - Optionally delete VPC network and firewall rules
    - Clean up local state

    \b
    Warning: All data on VMs will be lost.
    """
    cmd = DownCommand(project, yes=yes, keep_infra=keep_infra, verbose=verbose)
    cmd.run()
