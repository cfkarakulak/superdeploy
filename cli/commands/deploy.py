"""SuperDeploy CLI - Deploy command"""

import click
import subprocess
import os
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--message", "-m", help="Commit message (optional)")
def deploy(project, app, message):
    """
    Deploy an application (direct push to Forgejo)
    
    This command will:
    1. Commit any changes in app-repos/<app>
    2. Push to Forgejo (triggers deployment)
    3. Show deployment logs
    
    \b
    Quick Deploy:
      superdeploy deploy -p <project> -a <app>
    
    \b
    With custom message:
      superdeploy deploy -p <project> -a <app> -m "Fix bug"
    """
    console.print(f"\n[bold cyan]🚀 Deploying {app}[/bold cyan]\n")
    
    # Find app directory
    app_dir = Path.home() / "Desktop/cheapa.io/hero/app-repos" / app
    
    if not app_dir.exists():
        console.print(f"[red]❌ App directory not found: {app_dir}[/red]")
        return
    
    try:
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=app_dir,
            capture_output=True,
            text=True
        )
        
        has_changes = bool(result.stdout.strip())
        
        if has_changes:
            console.print("[yellow]📝 Committing changes...[/yellow]")
            
            # Add all changes
            subprocess.run(["git", "add", "-A"], cwd=app_dir, check=True)
            
            # Commit
            commit_msg = message or f"Deploy {app}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=app_dir,
                check=True,
                capture_output=True
            )
            console.print("[green]✓ Changes committed[/green]")
        else:
            console.print("[dim]No changes to commit[/dim]")
        
        # Push to production
        console.print("[yellow]📤 Pushing to Forgejo...[/yellow]")
        result = subprocess.run(
            ["git", "push", "origin", "production"],
            cwd=app_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Pushed to production[/green]")
            console.print("\n[bold]Deployment triggered![/bold]")
            console.print(f"\n[dim]Monitor logs:[/dim]")
            console.print(f"  [green]superdeploy logs -p {project} -a {app} -f[/green]\n")
        else:
            console.print(f"[red]❌ Push failed:[/red]")
            console.print(result.stderr)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
