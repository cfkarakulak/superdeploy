"""SuperDeploy CLI - Scale command"""

import click
from rich.console import Console
from rich.panel import Panel

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
    console.print(
        Panel.fit(
            f"[bold cyan]📊 Scale Infrastructure[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]VM Role: {vm_role}[/white]\n"
            f"[white]Target Count: {count}[/white]",
            border_style="cyan",
        )
    )
    
    console.print("\n[bold]Steps:[/bold]")
    console.print(f"1. Edit [green]projects/{project}/project.yml[/green]:")
    console.print(f"   [dim]vms:")
    console.print(f"     {vm_role}:")
    console.print(f"       count: {count}[/dim]\n")
    
    console.print("2. Apply changes:")
    console.print(f"   [cyan]superdeploy up -p {project}[/cyan]\n")
    
    console.print("[yellow]Note:[/yellow] Add load balancer (Caddy) to distribute traffic across VMs\n")
