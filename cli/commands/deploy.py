"""Deploy command - Simplified for GitHub Actions deployment"""

import click
from rich.console import Console

console = Console()


@click.command(name="deploy")
@click.option("-a", "--app", required=True, help="App name")
@click.option("-m", "--message", default="Deploy", help="Commit message")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def deploy(project, app, message, verbose):
    """
    Deploy an application (via GitHub Actions)

    This command will:
    1. Show deployment instructions
    2. Guide you through GitHub Actions deployment

    Example:
        superdeploy deploy -p myproject -a api
    """

    console.print("\n[bold cyan]📦 Deployment Guide[/bold cyan]\n")
    console.print(f"Project: [cyan]{project}[/cyan]")
    console.print(f"App: [cyan]{app}[/cyan]\n")

    console.print("[bold]To deploy your application:[/bold]\n")
    console.print("1. Commit your changes:")
    console.print(f"   [dim]cd ~/code/{project}/{app}[/dim]")
    console.print("   [dim]git add .[/dim]")
    console.print(f'   [dim]git commit -m "{message}"[/dim]\n')

    console.print("2. Push to production branch:")
    console.print("   [dim]git push origin production[/dim]\n")

    console.print("3. Monitor deployment:")
    console.print(f"   [dim]https://github.com/yourorg/{app}/actions[/dim]\n")

    console.print(
        "[green]✅ GitHub Actions will automatically deploy your app![/green]"
    )
