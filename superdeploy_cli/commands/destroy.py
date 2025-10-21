"""SuperDeploy CLI - Destroy command"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from superdeploy_cli.utils import load_env, get_project_root, run_command

console = Console()


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--keep-network", is_flag=True, help="Keep VPC network (only delete VMs)")
def destroy(yes, keep_network):
    """
    Destroy all infrastructure (like 'heroku apps:destroy')

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
            "[bold red]⚠️  SuperDeploy Infrastructure Destruction[/bold red]\n\n"
            "[white]This will permanently delete all VMs and data![/white]",
            border_style="red",
        )
    )

    env = load_env()
    project_root = get_project_root()

    # Load GCP project info
    gcp_project = env.get("GCP_PROJECT_ID")
    gcp_region = env.get("GCP_REGION", "us-central1")

    if not gcp_project:
        console.print("[red]❌ GCP_PROJECT_ID not found in .env[/red]")
        raise SystemExit(1)

    # Show what will be destroyed
    console.print("\n[bold yellow]📋 Resources to be destroyed:[/bold yellow]")

    try:
        # List VMs
        result = subprocess.run(
            [
                "gcloud",
                "compute",
                "instances",
                "list",
                f"--project={gcp_project}",
                "--format=value(name,zone)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout.strip():
            vm_count = len(result.stdout.strip().split("\n"))
            console.print(f"  • [cyan]{vm_count} VM(s)[/cyan]")
            for line in result.stdout.strip().split("\n"):
                if line:
                    name, zone = line.split("\t")
                    console.print(f"    - {name} ({zone})")
        else:
            console.print("  • [dim]No VMs found[/dim]")

        if not keep_network:
            console.print("  • [cyan]VPC Network & Firewall Rules[/cyan]")

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not list resources: {e}[/yellow]")

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

    # Method 1: Use gcloud to delete VMs directly (faster)
    try:
        result = subprocess.run(
            [
                "gcloud",
                "compute",
                "instances",
                "list",
                f"--project={gcp_project}",
                "--format=value(name,zone)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line:
                    name, zone = line.split("\t")
                    console.print(f"  Deleting VM: [cyan]{name}[/cyan]...")
                    subprocess.run(
                        [
                            "gcloud",
                            "compute",
                            "instances",
                            "delete",
                            name,
                            f"--zone={zone}",
                            f"--project={gcp_project}",
                            "--quiet",
                        ],
                        check=True,
                        capture_output=True,
                    )
                    console.print(f"    ✓ [green]Deleted {name}[/green]")

        console.print("\n[green]✅ All VMs destroyed![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Error deleting VMs: {e}[/red]")
        console.print("[yellow]Falling back to Terraform destroy...[/yellow]")

        # Fallback: Use terraform destroy
        terraform_dir = project_root / "terraform"
        console.print("\n[cyan]Running terraform destroy...[/cyan]")
        run_command("./terraform-wrapper.sh destroy -auto-approve", cwd=terraform_dir)

    # Optionally destroy network
    if not keep_network:
        console.print("\n[cyan]🗑️  Destroying VPC network...[/cyan]")
        try:
            terraform_dir = project_root / "terraform"
            run_command(
                "./terraform-wrapper.sh destroy -auto-approve", cwd=terraform_dir
            )
            console.print("[green]✅ Network destroyed![/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Network destruction skipped: {e}[/yellow]")

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Destruction Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(
        "\n[white]To deploy again, run:[/white] [cyan]superdeploy up[/cyan]\n"
    )
