import os

"""SuperDeploy CLI - Run command"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from cli.utils import load_env, validate_env_vars
from cli.logger import DeployLogger

console = Console()


@click.command(name="run")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.argument("app")
@click.argument("command")
def run(project, app, command, verbose):
    """
    Run one-off command in app container

    \b
    Examples:
      superdeploy run api "python manage.py migrate"
      superdeploy run api "bash"
      superdeploy run dashboard "npm install"
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    
    if not verbose:
        console.print(
            Panel.fit(
                f"[bold cyan]⚡ Run Command[/bold cyan]\n\n"
                f"[white]Project: {project}[/white]\n"
                f"[white]App: {app}[/white]\n"
                f"[white]Command: {command}[/white]",
                border_style="cyan",
            )
        )
    
    logger = DeployLogger(project, f"run-{app}", verbose=verbose)
    
    # Load config to find VM
    logger.step("Loading project configuration")
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        logger.success("Configuration loaded")
        
        if app not in apps:
            logger.log_error(f"App '{app}' not found in project config")
            raise SystemExit(1)
        
        vm_role = apps[app].get("vm", "core")
        
        # Get VM IP from .env
        from cli.utils import load_env
        env = load_env(project=project)
        
        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            logger.log_error(f"VM IP not found in .env: {ip_key}")
            logger.log(f"Run: superdeploy up -p {project}")
            raise SystemExit(1)
        
        ssh_host = env[ip_key]
        logger.log(f"Found VM: {ssh_host}")
        
    except Exception as e:
        logger.log_error(f"Error: {e}")
        raise SystemExit(1)
    
    # SSH config
    logger.step(f"Executing command in {app} container")
    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"

    # Use -i (not -it) for non-interactive commands to avoid TTY errors
    docker_cmd = f"docker exec -i {project}-{app} {command}"

    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        f"{ssh_user}@{ssh_host}",
        docker_cmd,
    ]

    try:
        result = subprocess.run(ssh_cmd, check=True)

        if result.returncode == 0:
            logger.success("Command executed successfully")
            if not verbose:
                console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    except subprocess.CalledProcessError as e:
        logger.log_error(f"Command failed with exit code {e.returncode}")
        raise SystemExit(e.returncode)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        raise SystemExit(130)
