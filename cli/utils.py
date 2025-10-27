"""SuperDeploy CLI - Utility functions"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import dotenv_values
from rich.console import Console

console = Console()


def find_env_file() -> Optional[Path]:
    """
    Smart .env file detection (DEPRECATED - for backward compatibility only)
    
    New behavior: SuperDeploy now uses environment variables instead of .env files.
    This function is kept for backward compatibility during migration.
    """
    search_paths = [
        Path.cwd() / ".env",
        Path.home() / ".superdeploy" / ".env",
        Path(__file__).parent.parent / ".env",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def load_env(project: Optional[str] = None) -> Dict[str, Any]:
    """
    Load environment configuration from project.yml.
    
    All configuration is now per-project in project.yml.
    This function loads the project config and converts it to env-like dict
    for backward compatibility with existing code.
    
    Args:
        project: Project name to load config from
    
    Returns:
        Dictionary of environment variables extracted from project.yml
    """
    if not project:
        console.print("[red]❌ Project name required![/red]")
        console.print("\n[cyan]Usage:[/cyan]")
        console.print("  superdeploy <command> -p <project>")
        raise SystemExit(1)
    
    # Load project config
    from cli.core.config_loader import ConfigLoader
    
    project_root = get_project_root()
    config_loader = ConfigLoader(project_root / "projects")
    
    try:
        project_config = config_loader.load_project(project)
    except FileNotFoundError:
        console.print(f"[red]❌ Project '{project}' not found![/red]")
        console.print(f"\n[cyan]Create it with:[/cyan]")
        console.print(f"  superdeploy init -p {project}")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]❌ Invalid project config: {e}[/red]")
        raise SystemExit(1)
    
    # Extract ALL non-sensitive config from project.yml
    config = project_config.raw_config
    cloud = config.get('cloud', {})
    gcp = cloud.get('gcp', {})
    ssh = cloud.get('ssh', {})
    docker_config = config.get('docker', {})
    
    # Get addons from new unified section
    addons = project_config.get_addons()
    forgejo = addons.get('forgejo', {})
    postgres = addons.get('postgres', {})
    rabbitmq = addons.get('rabbitmq', {})
    
    # Get GitHub config
    github_config = config.get('github', {})
    
    env_vars = {
        # GCP
        'GCP_PROJECT_ID': gcp.get('project_id'),
        'GCP_REGION': gcp.get('region', 'us-central1'),
        'GCP_ZONE': gcp.get('zone', 'us-central1-a'),
        
        # SSH
        'SSH_KEY_PATH': ssh.get('key_path'),
        'SSH_PUBLIC_KEY_PATH': ssh.get('public_key_path'),
        'SSH_USER': ssh.get('user'),
        
        # Docker
        'DOCKER_REGISTRY': docker_config.get('registry', 'docker.io'),
        'DOCKER_ORG': docker_config.get('organization'),
        'DOCKER_USERNAME': docker_config.get('username'),
        
        # GitHub
        'GITHUB_ORG': github_config.get('organization'),
        'GITHUB_REPO': github_config.get('repository'),
        
        # Forgejo (all non-sensitive config from project.yml)
        'FORGEJO_PORT': str(forgejo.get('port')),
        'FORGEJO_SSH_PORT': str(forgejo.get('ssh_port')),
        'FORGEJO_ORG': forgejo.get('org'),
        'FORGEJO_ADMIN_USER': forgejo.get('admin_user'),
        'FORGEJO_ADMIN_EMAIL': forgejo.get('admin_email'),
        'FORGEJO_REPO': forgejo.get('repo'),
        'FORGEJO_DB_NAME': forgejo.get('db_name'),
        'FORGEJO_DB_USER': forgejo.get('db_user'),
        'REPO_SUPERDEPLOY': forgejo.get('repo'),
        
        # Postgres (non-sensitive config)
        'POSTGRES_USER': postgres.get('user'),
        'POSTGRES_DB': postgres.get('database'),
        
        # RabbitMQ (non-sensitive config)
        'RABBITMQ_USER': rabbitmq.get('user'),
        
        # Monitoring
        'ENABLE_MONITORING': str(config.get('monitoring', {}).get('enabled', True)).lower(),
    }
    
    # Load sensitive values from project's .env file
    project_path = project_root / "projects" / project
    project_env_file = project_path / ".env"
    if project_env_file.exists():
        from dotenv import dotenv_values
        env_secrets = dotenv_values(project_env_file)
        env_vars.update(env_secrets)
    
    # Override with environment variables if set (for CI/CD)
    sensitive_vars = ['DOCKER_TOKEN', 'GITHUB_TOKEN', 'FORGEJO_PAT']
    for var in sensitive_vars:
        if var in os.environ:
            env_vars[var] = os.environ[var]
    
    console.print(f"[dim]✓ Loaded config from project.yml[/dim]")
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
        console.print("[red]❌ Missing required environment variables:[/red]")
        for key in missing:
            console.print(f"  • {key}")
        console.print("\n[cyan]Solution:[/cyan]")
        console.print("  Set the missing variables in your environment:")
        for key in missing:
            console.print(f"  export {key}='your-value'")
        console.print("\n[dim]See docs/ENVIRONMENT_VARIABLES.md for details[/dim]")
        return False

    return True
