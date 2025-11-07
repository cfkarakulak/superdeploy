"""SuperDeploy CLI - Utility functions"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict
from rich.console import Console

console = Console()


def get_available_projects() -> list:
    """Get list of available projects"""
    project_root = get_project_root()
    projects_dir = project_root / "projects"

    if not projects_dir.exists():
        return []

    return [
        d.name
        for d in projects_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]


def validate_project(project: str) -> None:
    """Validate that project exists"""
    available = get_available_projects()

    if not available:
        console.print("[red]❌ No projects found in projects/ directory![/red]")
        raise SystemExit(1)

    if project not in available:
        console.print(f"[red]❌ Project '{project}' not found![/red]")
        console.print("\n[yellow]Available projects:[/yellow]")
        for p in available:
            console.print(f"  • {p}")
        raise SystemExit(1)


def get_project_path(project: str) -> Path:
    """Get project directory path"""
    validate_project(project)
    return get_project_root() / "projects" / project


def run_command(
    cmd: str,
    cwd: Optional[str] = None,
    env: Optional[Dict] = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run shell command with better error handling"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            env={**os.environ, **(env or {})},
            capture_output=capture_output,
            text=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Command failed:[/red] {cmd}")
        if e.stderr:
            console.print(f"[red]{e.stderr}[/red]")
        raise SystemExit(1)


def ssh_command(
    host: str, user: str, key_path: str, cmd: str, silent_on_error: bool = False
) -> str:
    """Run SSH command on remote host

    Args:
        host: Remote host IP/hostname
        user: SSH user
        key_path: Path to SSH private key
        cmd: Command to run
        silent_on_error: If True, raises exception instead of printing and exiting

    Returns:
        Command output as string

    Raises:
        subprocess.CalledProcessError: If silent_on_error=True and command fails
    """
    import os

    # Expand ~ to actual home directory
    expanded_key_path = os.path.expanduser(key_path)
    ssh_cmd = (
        f"ssh -i {expanded_key_path} -o StrictHostKeyChecking=no {user}@{host} '{cmd}'"
    )

    if silent_on_error:
        # Don't print errors, just raise exception
        result = subprocess.run(
            ssh_cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    else:
        result = run_command(ssh_cmd, capture_output=True)
        return result.stdout.strip()


def get_project_root() -> Path:
    """
    Get SuperDeploy project root directory.

    Returns:
        Path to superdeploy directory (contains projects/, addons/, etc.)
    """
    # Start from current file location and go up to find superdeploy root
    current = Path(__file__).resolve()

    # Go up from cli/utils.py -> cli/ -> superdeploy/
    return current.parent.parent


def validate_env_vars(env: Dict, required_keys: list) -> bool:
    """
    Validate required environment variables are present.

    Args:
        env: Dictionary of environment variables
        required_keys: List of required variable names

    Returns:
        True if all required variables are present, False otherwise
    """
    missing = [key for key in required_keys if not env.get(key)]

    if missing:
        from rich.console import Console

        c = Console(force_terminal=True, legacy_windows=False)
        c.print("[red]✗ Missing required environment variables:[/red]")
        for key in missing:
            c.print(f"  • {key}")
        c.print("\n[cyan]Solution:[/cyan]")
        c.print("  Add these to your project.yml or secrets.yml")
        return False

    return True
