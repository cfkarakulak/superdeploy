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
        logger.step("[1/3] Preparing Destruction")

        # Check if we need to run terraform
        skip_terraform = self._prepare_destruction(logger)

        if not skip_terraform:
            logger.step("[2/3] Terraform Destroy")
            self._terraform_destroy(logger)

        logger.step("[3/3] Manual Cleanup")
        self._manual_cleanup(logger)

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

    def _prepare_destruction(self, logger) -> bool:
        """Prepare for destruction. Returns True if should skip terraform."""
        from cli.terraform_utils import workspace_exists

        # Delete state.yml FIRST (before any operations that might fail)
        state_file = self.project_root / "projects" / self.project_name / "state.yml"
        if state_file.exists():
            try:
                state_file.unlink()
                self.console.print("  [dim]✓ State file removed[/dim]")
            except Exception as e:
                self.console.print(
                    f"  [yellow]⚠ Could not delete state.yml: {e}[/yellow]"
                )

        # Load project config
        from cli.core.config_loader import ConfigLoader

        projects_dir = self.project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        try:
            project_config = config_loader.load_project(self.project_name)
            self.console.print("  [dim]✓ Configuration loaded[/dim]")
        except FileNotFoundError:
            self.console.print(
                "  [dim]✓ Configuration not found (project may not exist)[/dim]"
            )

        terraform_dir = self.project_root / "shared" / "terraform"

        # Clean state lock
        lock_file = (
            terraform_dir
            / "terraform.tfstate.d"
            / self.project_name
            / ".terraform.tfstate.lock.info"
        )
        if lock_file.exists():
            lock_file.unlink()
            self.console.print("  [dim]✓ State locks cleaned[/dim]")

        # Check if workspace exists
        if not workspace_exists(self.project_name):
            self.console.print("  [dim]✓ No workspace found (already destroyed)[/dim]")
            return True

        return False

    def _terraform_destroy(self, logger) -> None:
        """Run terraform destroy."""
        from cli.terraform_utils import terraform_init, select_workspace
        from cli.logger import run_with_progress

        terraform_dir = self.project_root / "shared" / "terraform"

        # Switch to default workspace before init
        subprocess.run(
            "terraform workspace select default 2>/dev/null || true",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
        )

        # Initialize Terraform
        try:
            terraform_init(quiet=True)
        except Exception as e:
            logger.warning(f"Init warning: {e}")

        # Select workspace
        try:
            select_workspace(self.project_name, create=False)
        except Exception as e:
            logger.warning(f"Workspace error: {e}")

        # Run destroy
        try:
            returncode, stdout, stderr = run_with_progress(
                logger,
                f"cd {terraform_dir} && terraform destroy -auto-approve -lock=false -no-color",
                "Destroying infrastructure (this may take 2-3 minutes)",
                cwd=self.project_root,
            )

            if returncode == 0:
                self.console.print("  [dim]✓ All resources destroyed[/dim]")
            else:
                logger.warning(f"Terraform destroy had issues: {stderr}")
                self.console.print("  ⚠ Partial destruction")

        except Exception as e:
            logger.log_error(f"Terraform destroy error: {e}")
            self.console.print("  ⚠ Partial destruction")

    def _manual_cleanup(self, logger) -> None:
        """Manual GCP and local cleanup."""
        # Get GCP config
        gcp_config = self.config_service.get_gcp_config(self.project_name)
        zone = gcp_config["zone"]
        region = gcp_config["region"]

        # GCP cleanup
        self._cleanup_gcp_resources(zone, region, logger)

        # Terraform state cleanup
        self._cleanup_terraform_state()

        # Release subnet
        self._release_subnet(logger)

        # Clean local files
        self._clean_local_files()

        self.console.print("  [dim]✓ Local files cleaned[/dim]")

    def _cleanup_gcp_resources(self, zone: str, region: str, logger) -> None:
        """Clean up GCP resources manually."""
        vms_deleted = 0
        firewalls_deleted = 0
        subnets_deleted = 0
        networks_deleted = 0
        ips_deleted = 0

        # Delete VMs first
        vm_list_cmd = f"gcloud compute instances list --filter='name~^{self.project_name}-' --format='value(name,zone)'"
        result = subprocess.run(vm_list_cmd, shell=True, capture_output=True, text=True)

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        vm_name, vm_zone = parts[0], parts[1]
                        subprocess.run(
                            f"gcloud compute instances delete {vm_name} --zone={vm_zone} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        vms_deleted += 1
            time.sleep(3)

        # Delete Firewall Rules
        fw_list_cmd = f"gcloud compute firewall-rules list --filter='network~{self.project_name}-network' --format='value(name)'"
        result = subprocess.run(fw_list_cmd, shell=True, capture_output=True, text=True)

        if result.stdout.strip():
            for fw_name in result.stdout.strip().split("\n"):
                if fw_name:
                    subprocess.run(
                        f"gcloud compute firewall-rules delete {fw_name} --quiet",
                        shell=True,
                        capture_output=True,
                    )
                    firewalls_deleted += 1

        # Delete Subnets
        subnet_list_cmd = f"gcloud compute networks subnets list --filter='network~{self.project_name}-network' --format='value(name,region)'"
        result = subprocess.run(
            subnet_list_cmd, shell=True, capture_output=True, text=True
        )

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        subnet_name, subnet_region = parts[0], parts[1]
                        subprocess.run(
                            f"gcloud compute networks subnets delete {subnet_name} --region={subnet_region} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        subnets_deleted += 1

        # Delete Network
        network_name = f"{self.project_name}-network"
        for attempt in range(3):
            result = subprocess.run(
                f"gcloud compute networks delete {network_name} --quiet",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                networks_deleted += 1
                break
            elif (
                "not found" in result.stderr.lower()
                or "was not found" in result.stderr.lower()
            ):
                break
            elif attempt < 2:
                time.sleep(2)

        # Delete External IPs
        ip_list_cmd = f"gcloud compute addresses list --filter='name~^{self.project_name}-' --format='value(name,region)'"
        result = subprocess.run(ip_list_cmd, shell=True, capture_output=True, text=True)

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_name, ip_region = parts[0], parts[1]
                        subprocess.run(
                            f"gcloud compute addresses delete {ip_name} --region={ip_region} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        ips_deleted += 1

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

    def _cleanup_terraform_state(self) -> None:
        """Clean up Terraform state workspace."""
        try:
            terraform_dir = self.project_root / "shared" / "terraform"

            # Switch to default workspace first
            subprocess.run(
                "terraform workspace select default",
                shell=True,
                cwd=terraform_dir,
                capture_output=True,
            )

            # Delete the project workspace (this also removes state)
            # Use -force because after destroy, state might have stale references
            result = subprocess.run(
                f"terraform workspace delete -force {self.project_name}",
                shell=True,
                cwd=terraform_dir,
                capture_output=True,
                text=True,
            )

            # If workspace deletion failed, manually remove state directory
            if result.returncode != 0:
                state_dir = terraform_dir / "terraform.tfstate.d" / self.project_name
                if state_dir.exists():
                    import shutil

                    shutil.rmtree(state_dir)

            self.console.print("  [dim]✓ Terraform state cleaned[/dim]")
        except Exception:
            pass

    def _release_subnet(self, logger) -> None:
        """Release subnet allocation."""
        try:
            from cli.subnet_allocator import SubnetAllocator

            allocator = SubnetAllocator()
            allocator.release_subnet(self.project_name)
        except Exception as e:
            logger.warning(f"Subnet release warning: {e}")

    def _clean_local_files(self) -> None:
        """Clean up local project files."""
        deleted_items = []

        # Delete state.yml (CRITICAL - always delete)
        state_file = self.project_root / "projects" / self.project_name / "state.yml"
        if state_file.exists():
            try:
                state_file.unlink()
                deleted_items.append("state.yml")
            except Exception as e:
                self.console.print(
                    f"  [yellow]⚠ Could not delete state.yml: {e}[/yellow]"
                )

        # Clean inventory file
        inventory_file = (
            self.project_root
            / "shared"
            / "ansible"
            / "inventories"
            / f"{self.project_name}.ini"
        )
        if inventory_file.exists():
            try:
                inventory_file.unlink()
                deleted_items.append("inventory")
            except Exception:
                pass

        # Clean tfvars
        terraform_dir = self.project_root / "shared" / "terraform"
        tfvars_file = terraform_dir / f"{self.project_name}.tfvars.json"
        if tfvars_file.exists():
            try:
                tfvars_file.unlink()
                deleted_items.append("tfvars")
            except Exception:
                pass

        if deleted_items:
            self.console.print(
                f"  [dim]✓ Local files cleaned ({', '.join(deleted_items)})[/dim]"
            )
        else:
            self.console.print("  [dim]✓ No local files to clean[/dim]")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
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
