"""SuperDeploy CLI - Promote command"""

import click
from rich.console import Console
from cli.ui_components import show_header

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name")
@click.option("--from-branch", default="staging", help="Source branch")
@click.option("--to-branch", default="production", help="Target branch")
def promote(project, app, from_branch, to_branch):
    """
    Promote code between environments using Git branches
    
    \b
    Example:
      superdeploy promote -p cheapa -a api
      # Merges staging → production and auto-deploys
    """
    console.print(f"\n[bold cyan]🚀 Promoting {app}: {from_branch} → {to_branch}[/bold cyan]\n")
    
    console.print("[bold]Run these commands:[/bold]")
    console.print(f"  [green]cd app-repos/{app}[/green]")
    console.print(f"  [green]git checkout {from_branch} && git pull[/green]")
    console.print(f"  [green]git checkout {to_branch}[/green]")
    console.print(f"  [green]git merge {from_branch}[/green]")
    console.print(f"  [green]git push origin {to_branch}[/green]  # Auto-deploys!\n")
    
    console.print("[dim]GitHub Actions will automatically deploy to production[/dim]\n")
