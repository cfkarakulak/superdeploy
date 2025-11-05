"""SuperDeploy CLI - Scale command"""

import click
from rich.console import Console
from cli.ui_components import show_header

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--vm-role", required=True, help="VM role (api, web, worker)")
@click.option("--count", type=int, required=True, help="Number of VMs")
def scale(project, vm_role, count):
    """
    Scale VMs for a service

    \b
    Example:
      superdeploy scale -p cheapa --vm-role api --count 3
    """
    show_header(
        title="Scale Infrastructure",
        project=project,
        details={"VM Role": vm_role, "Target Count": str(count)},
        console=console,
    )

    console.print("\n[bold]Steps:[/bold]")
    console.print(f"1. Edit [green]projects/{project}/project.yml[/green]:")
    console.print("   [dim]vms:")
    console.print(f"     {vm_role}:")
    console.print(f"       count: {count}[/dim]\n")

    console.print("2. Apply changes:")
    console.print(f"   [red]superdeploy up -p {project}[/red]\n")

    console.print(
        "[yellow]Note:[/yellow] Add load balancer (Caddy) to distribute traffic across VMs\n"
    )
