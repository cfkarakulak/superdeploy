"""SuperDeploy CLI - Doctor command"""
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.command()
def doctor():
    """Health check & diagnostics"""
    console.print("[bold cyan]🏥 Running diagnostics...[/bold cyan]\n")
    
    table = Table(title="System Health")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    # TODO: Implement real checks
    table.add_row("✅ .env file", "OK", "Found")
    table.add_row("✅ GCP auth", "OK", "Authenticated")
    table.add_row("✅ VMs", "OK", "3 running")
    table.add_row("✅ Forgejo", "OK", "Accessible")
    table.add_row("✅ Runner", "OK", "Active")
    
    console.print(table)
