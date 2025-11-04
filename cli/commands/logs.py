import os

"""SuperDeploy CLI - Logs command"""

import click
import subprocess
from rich.console import Console
from cli.ui_components import show_header
from cli.logger import DeployLogger

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-f", "--follow", is_flag=True, help="Follow logs (tail -f)")
@click.option("-n", "--lines", default=100, help="Number of lines")
@click.option("-e", "--env", "environment", default="production", help="Environment")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def logs(project, app, follow, lines, environment, verbose):
    """
    View application logs

    \b
    Examples:
      superdeploy logs -a api              # Last 100 lines
      superdeploy logs -a api -f           # Follow logs
      superdeploy logs -a api -n 500       # Last 500 lines
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader

    if not verbose:
        show_header(
            title="Application Logs",
            project=project,
            app=app,
            details={"Follow": "Yes" if follow else "No", "Lines": str(lines)},
            console=console,
        )

    logger = DeployLogger(project, f"logs-{app}", verbose=verbose)

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

    # SSH config
    ssh_key = os.path.expanduser(ssh_key_path)

    follow_flag = "-f" if follow else ""
    # Container naming: {project}-{app}
    docker_cmd = f"docker logs {follow_flag} --tail {lines} {project}-{app} 2>&1"

    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        f"{ssh_user}@{ssh_host}",
        docker_cmd,
    ]

    process = None
    try:
        # Stream logs to terminal
        logger.step(f"Streaming logs from {app}")
        logger.log("Press Ctrl+C to stop")

        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if process.stdout:
            for line in process.stdout:
                print(line, end="")

        process.wait()
        logger.success("Log streaming complete")

    except KeyboardInterrupt:
        logger.warning("Stopped by user")
        if process:
            process.terminate()
    except subprocess.CalledProcessError as e:
        logger.log_error(f"Failed to fetch logs: {e}")
        raise SystemExit(1)
