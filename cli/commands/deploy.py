"""SuperDeploy CLI - Deploy command"""

import click
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from cli.logger import DeployLogger

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--message", "-m", help="Commit message (optional)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def deploy(project, app, message, verbose):
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
    if not verbose:
        console.print(
            Panel.fit(
                f"[bold cyan]🚀 Deploying {app}[/bold cyan]\n\n"
                f"[white]Project: {project}[/white]",
                border_style="cyan",
            )
        )

    # Initialize logger
    logger = DeployLogger(project, f"deploy-{app}", verbose=verbose)

    from rich.console import Console

    console = Console()

    logger.step("[1/2] Preparing Deployment")

    # Find app directory
    app_dir = Path.home() / "Desktop/cheapa.io/hero/app-repos" / app

    if not app_dir.exists():
        logger.log_error(f"App directory not found: {app_dir}")
        raise SystemExit(1)

    console.print(f"  ✓ Located {app}")

    try:
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=app_dir,
            capture_output=True,
            text=True,
        )

        has_changes = bool(result.stdout.strip())

        if has_changes:
            # Add all changes
            subprocess.run(["git", "add", "-A"], cwd=app_dir, check=True)

            # Commit
            commit_msg = message or f"Deploy {app}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=app_dir,
                check=True,
                capture_output=True,
            )
            console.print("  ✓ Changes committed")
        else:
            console.print("  ✓ No changes to commit")

        logger.step("[2/2] Deploying to Production")

        # Push to production
        result = subprocess.run(
            ["git", "push", "origin", "production"],
            cwd=app_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            console.print("  ✓ Pushed to production")

            if not verbose:
                console.print(
                    "\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]"
                )
                console.print("[bold green]✅ Deployment Triggered![/bold green]")
                console.print(
                    "[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]"
                )
                console.print("\n[dim]Monitor logs:[/dim]")
                console.print(
                    f"  [cyan]superdeploy logs -p {project} -a {app} -f[/cyan]"
                )
                console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
        else:
            logger.log_error("Push failed", context=result.stderr)
            raise SystemExit(1)

    except subprocess.CalledProcessError as e:
        logger.log_error(f"Git command failed: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.log_error(f"Unexpected error: {e}")
        raise SystemExit(1)
