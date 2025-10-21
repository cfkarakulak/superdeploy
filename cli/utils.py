"""SuperDeploy CLI - Utility functions"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import dotenv_values
from rich.console import Console

console = Console()


def find_env_file() -> Optional[Path]:
    """Smart .env file detection"""
    search_paths = [
        Path.cwd() / ".env",
        Path.home() / ".superdeploy" / ".env",
        Path(__file__).parent.parent / ".env",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def load_env() -> Dict[str, Any]:
    """Load .env file with smart detection"""
    env_file = find_env_file()

    if not env_file:
        console.print("[red]❌ Error: .env file not found![/red]")
        console.print("\n[yellow]Searched locations:[/yellow]")
        console.print(f"  • {Path.cwd() / '.env'}")
        console.print(f"  • {Path.home() / '.superdeploy' / '.env'}")
        console.print("\n[cyan]Solution:[/cyan]")
        console.print("  1. cd to your superdeploy directory")
        console.print("  2. Or run: [bold]superdeploy init[/bold]")
        raise SystemExit(1)

    env_vars = dotenv_values(env_file)
    env_vars["ENV_FILE_PATH"] = str(env_file)  # Store path for later use
    console.print(f"[dim]Loaded: {env_file}[/dim]")
    return env_vars


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


def ssh_command(host: str, user: str, key_path: str, cmd: str) -> str:
    """Run SSH command on remote host"""
    import os

    # Expand ~ to actual home directory
    expanded_key_path = os.path.expanduser(key_path)
    ssh_cmd = (
        f"ssh -i {expanded_key_path} -o StrictHostKeyChecking=no {user}@{host} '{cmd}'"
    )
    result = run_command(ssh_cmd, capture_output=True)
    return result.stdout.strip()


def get_project_root() -> Path:
    """Get project root directory"""
    env_file = find_env_file()
    if env_file:
        return env_file.parent
    return Path.cwd()


def validate_env_vars(env: Dict, required_keys: list) -> bool:
    """Validate required env vars are present"""
    missing = [key for key in required_keys if not env.get(key)]

    if missing:
        console.print("[red]❌ Missing required env vars:[/red]")
        for key in missing:
            console.print(f"  • {key}")
        return False

    return True
