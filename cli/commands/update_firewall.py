"""
Update firewall rules after port changes
"""

import click
from rich.console import Console
from cli.ui_components import show_header

console = Console()


@click.command()
def update_firewall(project):
    """
    Update firewall rules after changing ports in config.yml

    This command:
    1. Reads updated ports from config.yml
    2. Updates only the firewall rules (doesn't touch VMs)
    3. Much faster than full terraform apply

    Example:
        # After changing port in config.yml:
        superdeploy update-firewall -p cheapa
    """
    show_header(
        title="Update Firewall Rules",
        project=project,
        subtitle="Fast firewall update without touching VMs",
        console=console,
    )

    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    from cli.terraform_utils import (
        get_terraform_dir,
        select_workspace,
        run_terraform_command,
        generate_tfvars,
    )

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    # Load config
    config_loader = ConfigLoader(projects_dir)
    try:
        project_config = config_loader.load_project(project)
        console.print(
            f"[dim]✓ Loaded config: {projects_dir / project}/config.yml[/dim]"
        )
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        return
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        return

    # Generate tfvars with updated ports
    terraform_dir = get_terraform_dir()
    tfvars_file = generate_tfvars(project_config)
    console.print("[dim]✓ Generated tfvars with updated ports[/dim]")

    # Select workspace
    select_workspace(project, create=False)

    # Apply only firewall changes
    console.print("\n[yellow]⚡ Updating firewall rules (this is fast)...[/yellow]")

    try:
        run_terraform_command(
            [
                "apply",
                "-target=module.network.google_compute_firewall.allow_app_ports[0]",
                f"-var-file={tfvars_file}",
                "-auto-approve",
            ]
        )

        console.print("\n[green]✅ Firewall rules updated successfully![/green]")
        console.print("\n[bold]📝 What changed:[/bold]")
        console.print(
            f"  • Updated allowed ports: {', '.join(project_config.to_terraform_vars()['app_ports'])}"
        )
        console.print(
            "\n[dim]Note: VMs were not touched, only firewall rules updated[/dim]"
        )

    except Exception as e:
        console.print(f"\n[red]❌ Failed to update firewall: {e}[/red]")
        console.print(
            "\n[yellow]💡 Tip: If firewall rule doesn't exist yet, run:[/yellow]"
        )
        console.print(f"   [red]superdeploy {project}:up[/red]")
