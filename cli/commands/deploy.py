"""SuperDeploy CLI - Deploy command"""

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
def deploy(project, app):
    """
    Deploy an application (via Git push)
    
    Deployments are fully automated via GitHub Actions.
    Simply push to the production branch to trigger deployment.
    
    \b
    Quick Deploy:
      cd app-repos/<app>
      git push origin production
    
    \b
    Check Status:
      superdeploy status -p <project>
      superdeploy logs -p <project> -a <app> -f
    """
    console.print(f"\n[bold cyan]🚀 Deploying {app}[/bold cyan]\n")
    console.print("Deployments are automated via GitHub Actions.\n")
    console.print("[bold]To deploy:[/bold]")
    console.print(f"  [green]cd app-repos/{app}[/green]")
    console.print(f"  [green]git push origin production[/green]\n")
    console.print("[bold]Monitor deployment:[/bold]")
    console.print(f"  [green]superdeploy logs -p {project} -a {app} -f[/green]\n")
