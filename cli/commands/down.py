"""SuperDeploy CLI - Down command (with improved logging and UX)"""

import click
import subprocess
from rich.console import Console
from cli.ui_components import show_header

# Confirmation prompts handled with console.print + input()
from cli.utils import get_project_root
from cli.terraform_utils import (
    get_terraform_dir,
    select_workspace,
    get_terraform_outputs,
)
from cli.core.config_loader import ConfigLoader
from cli.logger import DeployLogger, run_with_progress

console = Console()


def clean_vm_ips_from_state(project_root, project):
    """Remove VM IP entries from state after destroying infrastructure"""
    from cli.state_manager import StateManager
    
    state_mgr = StateManager(project_root, project)
    state = state_mgr.load_state()
    
    if state and "vms" in state:
        # Clear VM IPs from state
        for vm_name in state["vms"]:
            if "external_ip" in state["vms"][vm_name]:
                del state["vms"][vm_name]["external_ip"]
            if "internal_ip" in state["vms"][vm_name]:
                del state["vms"][vm_name]["internal_ip"]
        
        state_mgr.save_state(state["config"], {"vms": state["vms"], "addons": state.get("addons", {}), "apps": state.get("apps", {})})
    
    console.print("  [dim]✓ Cleaned VM IPs from state[/dim]")


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
    project_root = get_project_root()

    # Initialize logger
    logger = DeployLogger(project, "down", verbose=verbose)

    if not verbose:
        show_header(
            title="Project Shutdown",
            subtitle="[bold red]This will stop all services and destroy all VMs![/bold red]",
            project=project,
            border_color="red",
            console=console,
        )

    # Load project config
    projects_dir = project_root / "projects"
    config_loader = ConfigLoader(projects_dir)

    try:
        project_config_obj = config_loader.load_project(project)
    except FileNotFoundError:
        logger.warning("Project config not found, will try to destroy anyway")
        project_config_obj = None

    env = load_env(project)

    # Load GCP project info
    gcp_project = env.get("GCP_PROJECT_ID")
    gcp_region = env.get("GCP_REGION", "us-central1")

    if not gcp_project:
        logger.warning("GCP_PROJECT_ID not found in .env")
        gcp_project = "unknown"

    # Show what will be destroyed
    if not verbose:
        console.print("[bold yellow]📋 Resources to be destroyed:[/bold yellow]")

    # Try to get resources from Terraform state
    try:
        select_workspace(project, create=False)
        outputs = get_terraform_outputs(project)

        if outputs and "vm_names" in outputs:
            vm_names = outputs["vm_names"].get("value", {})
            if vm_names:
                console.print(f"  • [cyan]{len(vm_names)} VM(s)[/cyan]")
                for key, name in vm_names.items():
                    console.print(f"    - {name}")
            else:
                console.print("  • [dim]No VMs in Terraform state[/dim]")
        else:
            console.print("  • [dim]No VMs in Terraform state[/dim]")

        if not keep_infra:
            console.print("  • [cyan]VPC Network & Firewall Rules[/cyan]")

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not read Terraform state: {e}[/yellow]")
        console.print("  • [dim]Will attempt destruction anyway[/dim]")

    # Confirmation
    if not yes:
        console.print(
            "\n[bold red]Are you sure you want to destroy all infrastructure?[/bold red] "
            "[bold bright_white]\\[y/n][/bold bright_white] [dim](n)[/dim]: ",
            end="",
        )
        answer = input().strip().lower()
        confirmed = answer in ["y", "yes"]

        if not confirmed:
            console.print("[yellow]❌ Destruction cancelled[/yellow]")
            raise SystemExit(0)

    console.print()  # Add 1 newline after confirmation
    logger.step("[1/3] Preparing Destruction")

    terraform_dir = get_terraform_dir()

    # Clean state lock (always)
    lock_file = (
        terraform_dir / "terraform.tfstate.d" / project / ".terraform.tfstate.lock.info"
    )
    if lock_file.exists():
        lock_file.unlink()

    console.print("  [dim]✓ State locks cleaned[/dim]")

    # Check if workspace exists
    from cli.terraform_utils import workspace_exists, terraform_init

    if not workspace_exists(project):
        console.print("  [dim]✓ No workspace found (already destroyed)[/dim]")
        skip_terraform = True
    else:
        skip_terraform = False
        console.print("  [dim]✓ Workspace found[/dim]")

    if not skip_terraform:
        logger.step("[2/3] Terraform Destroy")
        # Switch to default workspace before init to avoid prompts
        terraform_dir = project_root / "shared" / "terraform"
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
            logger.warning(f"  Init warning: {e}")

        # Select workspace
        try:
            select_workspace(project, create=False)
        except Exception as e:
            logger.warning(f"  Workspace error: {e}")

        # Run Terraform destroy with spinner
        try:
            returncode, stdout, stderr = run_with_progress(
                logger,
                f"cd {terraform_dir} && terraform destroy -auto-approve -lock=false -no-color",
                "Destroying infrastructure (this may take 2-3 minutes)",
                cwd=project_root,
            )

            if returncode == 0:
                console.print("  [dim]✓ All resources destroyed[/dim]")
            else:
                logger.warning(f"Terraform destroy had issues: {stderr}")
                console.print("  ⚠ Partial destruction")

        except Exception as e:
            logger.log_error(f"Terraform destroy error: {e}")
            console.print("  ⚠ Partial destruction")

    # Manual GCP cleanup if needed
    if not skip_terraform:
        logger.step("[3/3] Manual Cleanup")

        # ALWAYS do manual GCP cleanup (more reliable than terraform destroy)

        import time

        # Get region/zone from config or use defaults
        if project_config_obj:
            gcp_config = project_config_obj.raw_config.get("cloud", {}).get("gcp", {})
            zone = gcp_config.get("zone", "us-central1-a")
            region = gcp_config.get("region", "us-central1")
        else:
            region = "us-central1"
            zone = "us-central1-a"

        try:
            vms_deleted = 0
            firewalls_deleted = 0
            subnets_deleted = 0

            # 1. Delete VMs FIRST (they block everything else)
            vm_list_cmd = f"gcloud compute instances list --filter='name~^{project}-' --format='value(name,zone)'"
            result = subprocess.run(
                vm_list_cmd, shell=True, capture_output=True, text=True
            )

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
                # Wait for VMs to be fully deleted
                time.sleep(3)

            # 2. Delete Firewall Rules (must be before network)
            fw_list_cmd = f"gcloud compute firewall-rules list --filter='network~{project}-network' --format='value(name)'"
            result = subprocess.run(
                fw_list_cmd, shell=True, capture_output=True, text=True
            )

            if result.stdout.strip():
                for fw_name in result.stdout.strip().split("\n"):
                    if fw_name:
                        subprocess.run(
                            f"gcloud compute firewall-rules delete {fw_name} --quiet",
                            shell=True,
                            capture_output=True,
                        )
                        firewalls_deleted += 1

            # 3. Delete Subnets (must be before network)
            subnet_list_cmd = f"gcloud compute networks subnets list --filter='network~{project}-network' --format='value(name,region)'"
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

            networks_deleted = 0
            ips_deleted = 0

            # 4. Delete Network (try multiple times, GCP can be slow)
            network_name = f"{project}-network"

            # Try up to 3 times with delay
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
                    # Retry after delay
                    time.sleep(2)

            # 5. Delete External IPs (can be done anytime, do it last)
            ip_list_cmd = f"gcloud compute addresses list --filter='name~^{project}-' --format='value(name,region)'"
            result = subprocess.run(
                ip_list_cmd, shell=True, capture_output=True, text=True
            )

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
                console.print(
                    f"  [dim]✓ GCP resources cleaned: {', '.join(resources)}[/dim]"
                )
            else:
                console.print("  [dim]✓ No GCP resources found[/dim]")

        except Exception as gcp_error:
            logger.warning(f"GCP cleanup error: {gcp_error}")
            console.print("  ⚠ Partial GCP cleanup")

        # Cleanup Terraform state workspace
        try:
            state_dir = terraform_dir / "terraform.tfstate.d" / project
            if state_dir.exists():
                import shutil

                shutil.rmtree(state_dir)
            console.print("  [dim]✓ Terraform state cleaned[/dim]")
        except Exception as cleanup_error:
            logger.warning(f"State cleanup warning: {cleanup_error}")

        # Release subnet allocation
        try:
            from cli.subnet_allocator import SubnetAllocator

            allocator = SubnetAllocator()
            allocator.release_subnet(project)
        except Exception as e:
            logger.warning(f"Subnet release warning: {e}")

        # Clean up local files
        clean_vm_ips_from_state(project_root, project)
        project_dir = projects_dir / project

        # Clean up inventory file
        inventory_file = (
            project_root / "shared" / "ansible" / "inventories" / f"{project}.ini"
        )
        if inventory_file.exists():
            inventory_file.unlink()

        # Clean up generated tfvars
        tfvars_file = terraform_dir / f"{project}.tfvars.json"
        if tfvars_file.exists():
            tfvars_file.unlink()

        console.print("  [dim]✓ Local files cleaned[/dim]")

    # Final summary
    if not verbose:
        console.print("\n[color(248)]Project destroyed.[/color(248)]")
