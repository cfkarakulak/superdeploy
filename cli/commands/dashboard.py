"""Dashboard management commands."""

import click
import subprocess
import sys
import time
from pathlib import Path


@click.command(name="dashboard:start")
def dashboard_start():
    """Start the dashboard server."""
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
    click.echo("🔧 Starting backend on port 8401...")
    click.echo("📋 Backend logs:")
    click.echo("-" * 60)

    backend_dir = dashboard_dir / "backend"
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8401",
            "--reload",
        ],
        cwd=backend_dir,
        # Don't capture output - let it print to terminal
        stdout=None,
        stderr=None,
    )

    # Give backend time to start
    click.echo("-" * 60)
    click.echo("⏳ Waiting for backend to start...")
    time.sleep(3)

    # Check if backend started successfully
    if backend_proc.poll() is not None:
        click.echo("❌ Backend failed to start")
        click.echo("💡 Check the error messages above for details")
        return

    # Start Next.js frontend
    click.echo("\n🎨 Starting frontend on port 8400...")
    click.echo("📋 Frontend logs:")
    click.echo("-" * 60)

    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", "8400"],
        cwd=frontend_dir,
        # Don't capture output - let it print to terminal
        stdout=None,
        stderr=None,
    )

    click.echo("\n✅ Dashboard running!")
    click.echo("   Frontend: http://localhost:8400")
    click.echo("   Backend:  http://localhost:8401")
    click.echo("\n   Press Ctrl+C to stop")

    # Open browser
    try:
        subprocess.run(["open", "http://localhost:8400"], check=False)
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
    """Ensure the superdeploy database exists."""
    import os

    try:
        # Check if database exists
        result = subprocess.run(
            ["psql", "-U", os.getenv("USER", "postgres"), "-lqt"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if "superdeploy" not in result.stdout:
            click.echo("📦 Creating database...")
            subprocess.run(
                ["createdb", "superdeploy"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            click.echo("✓ Database created")
        else:
            click.echo("✓ Database exists")
    except Exception as e:
        click.echo(f"⚠ Database check warning: {e}")
