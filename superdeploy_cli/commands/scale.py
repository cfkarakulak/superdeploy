"""SuperDeploy CLI - Scale command"""
import click
from rich.console import Console

console = Console()

@click.command()
@click.argument('scale_spec')
def scale(scale_spec):
    """Scale service (e.g. api=3)"""
    app, replicas = scale_spec.split('=')
    console.print(f"[cyan]📊 Scaling {app} to {replicas} replicas...[/cyan]")
    # TODO: Implement docker compose scale
