"""SuperDeploy CLI - Status command"""
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.command()
def status():
    """Show infrastructure status"""
    table = Table(title="Infrastructure Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("IP", style="yellow")
    
    # TODO: Fetch real status
    table.add_row("Core VM", "✅ Running", "34.56.78.90")
    table.add_row("Forgejo", "✅ Active", "http://34.56.78.90:3001")
    table.add_row("Runner", "✅ Registered", "core-runner")
    
    console.print(table)
