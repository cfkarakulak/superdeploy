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

        # Get VM IP from inventory
        inventory_path = (
            project_root / "shared" / "ansible" / "inventories" / f"{project}.ini"
        )
        if not inventory_path.exists():
            console.print(
                f"[red]❌ Inventory not found. Run: superdeploy up -p {project}[/red]"
            )
            return

        # Parse inventory to get VM IP
        inventory_content = inventory_path.read_text()
        import re

        pattern = rf"{project}-{vm_role}-\d+\s+ansible_host=(\S+)"
        match = re.search(pattern, inventory_content)

        if not match:
            logger.log_error(f"VM not found in inventory for role: {vm_role}")
            raise SystemExit(1)

        ssh_host = match.group(1)
        logger.log(f"Found VM: {ssh_host}")

    except Exception as e:
        logger.log_error(f"Error: {e}")
        raise SystemExit(1)

    # SSH config
    ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
    ssh_user = "superdeploy"

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
