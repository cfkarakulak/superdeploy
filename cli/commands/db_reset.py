"""Database reset command."""

from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm
from cli.ui_components import show_header


def db_reset():
    """Reset database - drop all tables and run migrations."""
    console = Console()

    show_header(
        title="Database Reset",
        subtitle="Drop all tables and run migrations",
        console=console,
    )

    console.print(
        "\n[bold red]⚠️  WARNING:[/bold red] This will [bold]DELETE ALL DATA[/bold] in the database!"
    )
    console.print(
        "[dim]All tables will be dropped and recreated from migrations.[/dim]\n"
    )

    # Confirmation
    if not Confirm.ask(
        "[bold yellow]Are you sure you want to reset the database?[/bold yellow]",
        default=False,
    ):
        console.print("\n[yellow]✗[/yellow] Database reset cancelled.")
        return

    console.print("\n[cyan]▶[/cyan] Dropping all tables...")

    try:
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()

        # List of tables to drop (in correct order due to foreign keys)
        tables_to_drop = [
            "processes",
            "secret_aliases",
            "secrets",
            "deployment_history",
            "activity_logs",
            "addons",
            "vms",
            "apps",
            "projects",
            "settings",
            "alembic_version",
        ]

        for table in tables_to_drop:
            try:
                db.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                console.print(f"  [dim]✓ Dropped {table}[/dim]")
            except Exception:
                console.print(f"  [dim]- {table} (not found)[/dim]")

        db.commit()
        db.close()

        console.print("\n[bold green]✓[/bold green] All tables dropped")

    except Exception as e:
        console.print(f"\n[bold red]✗[/bold red] Error dropping tables: {e}")
        return

    # Run migrations
    console.print("\n[cyan]▶[/cyan] Running migrations...")

    try:
        import subprocess

        backend_dir = Path(__file__).parent.parent.parent / "dashboard" / "backend"

        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=backend_dir,
        )

        if result.returncode == 0:
            console.print(
                "\n[bold green]✓[/bold green] Database reset complete! All tables recreated."
            )
        else:
            console.print("\n[bold red]✗[/bold red] Migration failed!")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")

    except Exception as e:
        console.print(f"\n[bold red]✗[/bold red] Error running migrations: {e}")
