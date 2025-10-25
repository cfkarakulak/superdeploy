"""SuperDeploy CLI - Down command"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from cli.utils import load_env, get_project_root, run_command

console = Console()


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
            f"[white]This will stop all services and optionally destroy VMs![/white]",
            border_style="red",
        )
    )

    env = load_env(project)
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

        if not keep_infra:
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

    # Use Terraform destroy to properly clean up all resources
    terraform_dir = project_root / "shared" / "terraform"
    
    # Add PROJECT_NAME to env for Terraform workspace selection
    terraform_env = {**env, 'PROJECT_NAME': project}
    
    try:
        console.print("[cyan]Running terraform destroy...[/cyan]")
        
        # Initialize terraform first to ensure workspace exists
        run_command("./terraform-wrapper.sh init", cwd=str(terraform_dir), env=terraform_env)
        
        # Destroy all resources in the project workspace
        run_command(
            "./terraform-wrapper.sh destroy -auto-approve", 
            cwd=str(terraform_dir), 
            env=terraform_env
        )
        
        console.print("\n[green]✅ All resources destroyed![/green]")

    except Exception as e:
        console.print(f"[red]❌ Error during terraform destroy: {e}[/red]")
        console.print("[yellow]⚠️  Some resources may still exist. Check GCP console.[/yellow]")

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Destruction Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(
        "\n[white]To deploy again, run:[/white] [cyan]superdeploy up[/cyan]\n"
    )
