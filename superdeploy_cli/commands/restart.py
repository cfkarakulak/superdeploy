"""SuperDeploy CLI - Restart command"""
import click
from rich.console import Console

console = Console()

@click.command()
@click.argument('app')
def restart(app):
    """Restart service"""
    console.print(f"[cyan]🔄 Restarting {app}...[/cyan]")
    # TODO: Implement docker compose restart
