"""Dashboard management commands."""

import click
import subprocess
import sys
import time
from pathlib import Path


@click.group()
def dashboard():
    """Dashboard management commands."""
    pass


@dashboard.command()
def run():
    """Run the dashboard server."""
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"

    click.echo("🚀 Starting SuperDeploy Dashboard...")

    # Check PostgreSQL
    click.echo("📦 Checking PostgreSQL...")
    if not check_postgres():
        click.echo("❌ PostgreSQL not running. Please start PostgreSQL first:")
        click.echo("   brew services start postgresql")
        return

    # Check if database exists, create if not
    click.echo("🗄️  Checking database...")
    ensure_database()

    # Install frontend dependencies if needed
    frontend_dir = dashboard_dir / "frontend"
    if not (frontend_dir / "node_modules").exists():
        click.echo("📦 Installing frontend dependencies...")
        try:
            subprocess.run(
                ["npm", "install"], cwd=frontend_dir, check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Failed to install dependencies: {e}")
            return

    # Start FastAPI backend in background
    click.echo("🔧 Starting backend on port 6001...")
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "dashboard.backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "6001",
            "--reload",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Give backend time to start
    time.sleep(2)

    # Check if backend started successfully
    if backend_proc.poll() is not None:
        click.echo("❌ Backend failed to start")
        return

    # Start Next.js frontend
    click.echo("🎨 Starting frontend on port 6000...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", "6000"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    click.echo("\n✅ Dashboard running!")
    click.echo("   Frontend: http://localhost:6000")
    click.echo("   Backend:  http://localhost:6001")
    click.echo("\n   Press Ctrl+C to stop")

    # Open browser
    try:
        subprocess.run(["open", "http://localhost:6000"], check=False)
    except:
        pass

    # Wait for processes
    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        click.echo("\n⏹️  Shutting down...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except:
            backend_proc.kill()
            frontend_proc.kill()


def check_postgres():
    """Check if PostgreSQL is running."""
    try:
        result = subprocess.run(
            ["pg_isready"], check=True, capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return False


def ensure_database():
    """Ensure the superdeploy_dashboard database exists."""
    import os

    try:
        # Check if database exists
        result = subprocess.run(
            ["psql", "-U", os.getenv("USER", "postgres"), "-lqt"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if "superdeploy_dashboard" not in result.stdout:
            click.echo("📦 Creating database...")
            subprocess.run(
                ["createdb", "superdeploy_dashboard"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            click.echo("✓ Database created")
        else:
            click.echo("✓ Database exists")
    except Exception as e:
        click.echo(f"⚠ Database check warning: {e}")
