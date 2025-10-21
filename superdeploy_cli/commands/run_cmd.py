"""SuperDeploy CLI - Run command"""
import click
from rich.console import Console

console = Console()

@click.command(name='run')
@click.argument('app')
@click.argument('command')
def run(app, command):
    """Run one-off command"""
    console.print(f"[cyan]⚡ Running on {app}: {command}[/cyan]")
    # TODO: Implement SSH + docker exec
