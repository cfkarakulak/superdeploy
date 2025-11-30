"""Database migration command."""

import subprocess
from pathlib import Path
from rich.console import Console
from cli.ui_components import show_header


def migrate():
    """Run database migrations using Alembic."""
    console = Console()

    show_header(
        title="Database Migrations",
        subtitle="Running Alembic migrations",
        console=console,
    )

    backend_dir = Path(__file__).parent.parent.parent / "dashboard" / "backend"

    try:
        # Check if alembic is installed
        result = subprocess.run(
            ["alembic", "--version"], capture_output=True, text=True, cwd=backend_dir
        )

        if result.returncode != 0:
            console.print("[bold red]✗[/bold red] Alembic is not installed!")
            console.print("[dim]Install it with: pip install alembic[/dim]")
            return

        console.print("[cyan]▶[/cyan] Running migrations...")

        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=backend_dir,
        )

        if result.returncode == 0:
            console.print(
                "[bold green]✓[/bold green] All migrations completed successfully!"
            )
            if result.stdout:
                console.print(result.stdout)
        else:
            console.print("[bold red]✗[/bold red] Migration failed!")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            if result.stdout:
                console.print(result.stdout)

    except FileNotFoundError:
        console.print("[bold red]✗[/bold red] Alembic command not found!")
        console.print("[dim]Install it with: pip install alembic[/dim]")
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Error running migrations: {e}")
