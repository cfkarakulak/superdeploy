"""SuperDeploy CLI - Deploy command"""
import click
from rich.console import Console

console = Console()

@click.command()
@click.option('-a', '--app', help='App name')
@click.option('-e', '--env', default='production', help='Environment')
def deploy(app, env):
    """Trigger deployment"""
    console.print(f"[cyan]🚀 Deploying {app} to {env}...[/cyan]")
    # TODO: Trigger Forgejo workflow
