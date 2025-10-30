"""SuperDeploy CLI - Down command"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from cli.utils import load_env, get_project_root
from cli.terraform_utils import (
    get_terraform_dir,
    select_workspace,
    terraform_destroy,
    get_terraform_outputs,
)
from cli.core.config_loader import ConfigLoader

console = Console()


def clean_vm_ips_from_env(project_root, project):
    """Remove VM IP entries from .env file after destroying infrastructure"""
    env_file = project_root / "projects" / project / ".env"

    if not env_file.exists():
        return

    with open(env_file, "r") as f:
        lines = f.readlines()

    # Filter out lines with VM IPs
    cleaned_lines = []
    for line in lines:
        # Skip lines that are VM IP entries (both EXTERNAL and INTERNAL)
        if "_EXTERNAL_IP=" in line or "_INTERNAL_IP=" in line:
            continue
        cleaned_lines.append(line)

    # Write back
    with open(env_file, "w") as f:
        f.writelines(cleaned_lines)

    console.print("  [green]✓[/green] Cleaned VM IPs from .env")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--keep-infra",
    is_flag=True,
    help="Keep shared infrastructure (only stop project services)",
)
def down(project, yes, keep_infra):
    """
    Stop and destroy project resources (like 'heroku apps:destroy')

    This command will:
    - Delete all VMs (core, scrape, proxy)
    - Optionally delete VPC network and firewall rules
    - Clean up local state

    \b
    Warning: This action is DESTRUCTIVE and cannot be undone!
    All data on VMs will be lost.
    """
    console.print(
        Panel.fit(
            f"[bold red]⚠️  SuperDeploy Project Shutdown[/bold red]\n\n"
            f"[white]Project: [bold]{project}[/bold][/white]\n"
            f"[white]This will stop all services and destroy all VMs![/white]",
            border_style="red",
        )
    )

    project_root = get_project_root()

    # Load project config
    projects_dir = project_root / "projects"
    config_loader = ConfigLoader(projects_dir)

    try:
        project_config_obj = config_loader.load_project(project)
        console.print("[dim]✓ Loaded config from project.yml[/dim]")
    except FileNotFoundError:
        console.print(
            "[yellow]⚠️  Project config not found, will try to destroy anyway[/yellow]"
        )
        project_config_obj = None

    env = load_env(project)

    # Load GCP project info
    gcp_project = env.get("GCP_PROJECT_ID")
    gcp_region = env.get("GCP_REGION", "us-central1")

    if not gcp_project:
        console.print("[red]❌ GCP_PROJECT_ID not found in .env[/red]")
        console.print("[yellow]💡 Trying to continue with Terraform state...[/yellow]")
        gcp_project = "unknown"

    # Show what will be destroyed
    console.print("\n[bold yellow]📋 Resources to be destroyed:[/bold yellow]")

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

    console.print("")

    # Confirmation
    if not yes:
        confirmed = Confirm.ask(
            "[bold red]Are you sure you want to destroy all infrastructure?[/bold red]",
            default=False,
        )

        if not confirmed:
            console.print("[yellow]❌ Destruction cancelled[/yellow]")
            raise SystemExit(0)

    console.print("\n[bold red]🗑️  Starting destruction...[/bold red]\n")

    terraform_dir = get_terraform_dir()

    # Step 1: Clean state lock (always)
    console.print("[cyan]🔓 Cleaning state locks...[/cyan]")
    lock_file = (
        terraform_dir / "terraform.tfstate.d" / project / ".terraform.tfstate.lock.info"
    )
    if lock_file.exists():
        lock_file.unlink()
        console.print("  [green]✓[/green] Removed state lock file")
    else:
        console.print("  [dim]✓ No locks to clean[/dim]")

    # Step 2: Initialize Terraform
    try:
        console.print("[cyan]Initializing Terraform...[/cyan]")
        from cli.terraform_utils import terraform_init

        terraform_init()
        console.print("  [green]✓[/green] Terraform initialized")
    except Exception as e:
        console.print(f"[yellow]⚠️  Init warning: {e}[/yellow]")
        console.print("[dim]Continuing anyway...[/dim]")

    # Step 3: Select workspace
    try:
        console.print(f"[cyan]Selecting workspace: {project}...[/cyan]")
        select_workspace(project, create=False)
        console.print("  [green]✓[/green] Workspace selected")
    except Exception as e:
        console.print(f"[yellow]⚠️  Workspace error: {e}[/yellow]")
        console.print("[dim]Continuing with cleanup anyway...[/dim]")

    # Step 4: Run Terraform destroy (always with lock bypass)
    try:
        console.print("\n[cyan]🔥 Running terraform destroy...[/cyan]")

        if project_config_obj:
            # Use terraform_utils for proper destroy (with lock bypass)
            terraform_destroy(
                project, project_config_obj, auto_approve=True, force=True
            )
        else:
            # Fallback: Run destroy with minimal config
            import subprocess

            cmd = ["terraform", "destroy", "-auto-approve", "-lock=false"]

            result = subprocess.run(
                cmd, cwd=terraform_dir, capture_output=False, text=True
            )

            if result.returncode != 0:
                console.print(
                    "[yellow]⚠️  Terraform destroy had issues, continuing with cleanup...[/yellow]"
                )

        console.print("\n[green]✅ All resources destroyed![/green]")

    except Exception as e:
        console.print(f"\n[yellow]⚠️  Terraform destroy error: {e}[/yellow]")
        console.print("[yellow]Attempting manual GCP cleanup...[/yellow]")

        # Manual GCP cleanup using gcloud
        if project_config_obj:
            try:
                console.print("\n[cyan]🗑️  Force cleaning GCP resources...[/cyan]")

                gcp_config = project_config_obj.raw_config.get("cloud", {}).get(
                    "gcp", {}
                )
                zone = gcp_config.get("zone", "us-central1-a")
                region = gcp_config.get("region", "us-central1")

                import subprocess

                # 1. Delete VMs
                console.print("  [cyan]Deleting VMs...[/cyan]")
                vm_list_cmd = f"gcloud compute instances list --filter='name~^{project}-' --format='value(name,zone)' 2>/dev/null || true"
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
                                    f"gcloud compute instances delete {vm_name} --zone={vm_zone} --quiet 2>/dev/null || true",
                                    shell=True,
                                    capture_output=True,
                                )
                                console.print(
                                    f"    [green]✓[/green] Deleted VM: {vm_name}"
                                )
                else:
                    console.print("    [dim]No VMs found[/dim]")

                # 2. Delete External IPs
                console.print("  [cyan]Deleting External IPs...[/cyan]")
                ip_list_cmd = f"gcloud compute addresses list --filter='name~^{project}-' --format='value(name,region)' 2>/dev/null || true"
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
                                    f"gcloud compute addresses delete {ip_name} --region={ip_region} --quiet 2>/dev/null || true",
                                    shell=True,
                                    capture_output=True,
                                )
                                console.print(
                                    f"    [green]✓[/green] Deleted IP: {ip_name}"
                                )
                else:
                    console.print("    [dim]No IPs found[/dim]")

                # 3. Delete Firewall Rules
                console.print("  [cyan]Deleting Firewall Rules...[/cyan]")
                fw_list_cmd = f"gcloud compute firewall-rules list --filter='name~^{project}-' --format='value(name)' 2>/dev/null || true"
                result = subprocess.run(
                    fw_list_cmd, shell=True, capture_output=True, text=True
                )

                if result.stdout.strip():
                    for fw_name in result.stdout.strip().split("\n"):
                        if fw_name:
                            subprocess.run(
                                f"gcloud compute firewall-rules delete {fw_name} --quiet 2>/dev/null || true",
                                shell=True,
                                capture_output=True,
                            )
                            console.print(
                                f"    [green]✓[/green] Deleted firewall: {fw_name}"
                            )
                else:
                    console.print("    [dim]No firewall rules found[/dim]")

                # 4. Delete Subnets
                console.print("  [cyan]Deleting Subnets...[/cyan]")
                subnet_name = f"{project}-network-subnet"
                result = subprocess.run(
                    f"gcloud compute networks subnets delete {subnet_name} --region={region} --quiet 2>/dev/null || true",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    console.print(f"    [green]✓[/green] Deleted subnet: {subnet_name}")
                else:
                    console.print("    [dim]No subnet found[/dim]")

                # 5. Delete Network
                console.print("  [cyan]Deleting Network...[/cyan]")
                network_name = f"{project}-network"
                result = subprocess.run(
                    f"gcloud compute networks delete {network_name} --quiet 2>/dev/null || true",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    console.print(
                        f"    [green]✓[/green] Deleted network: {network_name}"
                    )
                else:
                    console.print("    [dim]No network found[/dim]")

                console.print("\n[green]✅ GCP resources cleaned![/green]")

            except Exception as gcp_error:
                console.print(f"[yellow]⚠️  GCP cleanup warning: {gcp_error}[/yellow]")
                console.print("[yellow]Some resources may still exist in GCP[/yellow]")

        # Cleanup Terraform state workspace
        try:
            console.print("\n[cyan]Cleaning up Terraform state...[/cyan]")
            state_dir = terraform_dir / "terraform.tfstate.d" / project
            if state_dir.exists():
                import shutil

                shutil.rmtree(state_dir)
                console.print("  [green]✓[/green] Removed state directory")
        except Exception as cleanup_error:
            console.print(f"[yellow]⚠️  State cleanup warning: {cleanup_error}[/yellow]")

    # Step 5: Release subnet allocation
    console.print("\n[cyan]Releasing subnet allocation...[/cyan]")
    try:
        from cli.subnet_allocator import SubnetAllocator
        allocator = SubnetAllocator()
        if allocator.release_subnet(project):
            console.print("  [green]✓[/green] Subnet released for reuse")
        else:
            console.print("  [dim]✓ No subnet allocation found[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Subnet release warning: {e}[/yellow]")

    # Step 6: Clean up local files
    console.print("\n[cyan]Cleaning up local files...[/cyan]")

    # Clean VM IPs from .env file
    clean_vm_ips_from_env(project_root, project)
    project_dir = projects_dir / project

    # Clean up inventory file
    inventory_file = (
        project_root / "shared" / "ansible" / "inventories" / f"{project}.ini"
    )
    if inventory_file.exists():
        inventory_file.unlink()
        console.print(f"  [green]✓[/green] Removed {inventory_file.name}")

    # Clean up generated tfvars
    tfvars_file = terraform_dir / f"{project}.tfvars.json"
    if tfvars_file.exists():
        tfvars_file.unlink()
        console.print(f"  [green]✓[/green] Removed {tfvars_file.name}")

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Destruction Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(
        "\n[white]To deploy again, run:[/white] [cyan]superdeploy up -p "
        + project
        + "[/cyan]\n"
    )
