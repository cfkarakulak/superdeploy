"""SuperDeploy CLI - Restart command"""

import click
import subprocess
from rich.console import Console
from pathlib import Path
from cli.ui_components import show_header
from cli.logger import DeployLogger

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def restart(project, app, verbose):
    """
    Restart an application container

    \b
    Example:
      superdeploy restart -p cheapa -a api
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader

    if not verbose:
        show_header(
            title="Restart Application",
            project=project,
            app=app,
            console=console,
        )

    logger = DeployLogger(project, f"restart-{app}", verbose=verbose)

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    # Load config to find VM
    logger.step("Loading project configuration")
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        logger.success("Configuration loaded")

        if app not in apps:
            logger.log_error(f"App '{app}' not found in project config")
            raise SystemExit(1)

        vm_role = apps[app].get("vm", "core")

        # Get SSH config from project config
        ssh_config = project_config.raw_config.get("cloud", {}).get("ssh", {})
        ssh_key_path = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")

        # Get VM IP from .env (source of truth)
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

    # SSH and restart container
    logger.step(f"Restarting {app} container")
    ssh_key = Path(ssh_key_path).expanduser()
    container_name = f"{project}-{app}"

    cmd = [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "StrictHostKeyChecking=no",
        f"{ssh_user}@{ssh_host}",
        f"docker restart {container_name}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.success(f"{app} restarted successfully")

        # Show status
        logger.log("Checking container status")
        status_cmd = [
            "ssh",
            "-i",
            str(ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            f"{ssh_user}@{ssh_host}",
            f"docker ps --filter name={container_name} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        ]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if not verbose:
            console.print("\n[cyan]Status:[/cyan]")
            console.print(status_result.stdout)
            console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    except subprocess.CalledProcessError as e:
        logger.log_error(f"Restart failed: {e.stderr}")
        raise SystemExit(1)
