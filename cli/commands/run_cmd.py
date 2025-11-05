"""SuperDeploy CLI - Run command"""

import os
import click
import subprocess
from rich.console import Console
from cli.logger import DeployLogger
from cli.ui_components import show_header

console = Console()


@click.command(name="run")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode (with TTY)")
@click.argument("app")
@click.argument("command")
def run(project, app, command, verbose, interactive):
    """
    Run one-off command in app container (like 'heroku run')

    \b
    Examples:
      superdeploy run -p cheapa api "python manage.py migrate"
      superdeploy run -p cheapa api bash -i
      superdeploy run -p cheapa dashboard "npm run build"

    \b
    Interactive commands (bash, sh, psql) are auto-detected.
    Use -i flag to force interactive mode.
    """
    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader

    if not verbose:
        show_header(
            title="Run Command",
            project=project,
            app=app,
            details={"Command": command},
            console=console,
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

        # Get SSH config from project config
        ssh_config = project_config.raw_config.get("cloud", {}).get("ssh", {})
        ssh_key_path = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")

        # Get VM IP from .env
        from cli.utils import load_env

        env = load_env(project=project)

        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            logger.log_error(f"VM IP not found in .env: {ip_key}")
            logger.log(f"Run: [red]superdeploy up -p {project}[/red]")
            raise SystemExit(1)

        ssh_host = env[ip_key]
        logger.log(f"Found VM: {ssh_host}")

    except Exception as e:
        logger.log_error(f"Error: {e}")
        raise SystemExit(1)

    # SSH config
    logger.step(f"Executing command in {app} container")
    ssh_key = os.path.expanduser(ssh_key_path)

    # Auto-detect interactive commands (bash, sh, psql, etc.)
    interactive_commands = [
        "bash",
        "sh",
        "zsh",
        "fish",
        "psql",
        "mysql",
        "redis-cli",
        "mongo",
        "mongosh",
    ]
    is_interactive = interactive or command.strip().split()[0] in interactive_commands

    # Find actual container name (try both formats)
    container_candidates = [
        f"{project}-{app}",  # new format
        f"{project}_{app}",  # old format
    ]

    logger.log("Finding container...")
    container_name = None
    for candidate in container_candidates:
        check_cmd = f"docker ps -q -f name={candidate}"
        ssh_check = [
            "ssh",
            "-i",
            ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            f"{ssh_user}@{ssh_host}",
            check_cmd,
        ]
        result = subprocess.run(ssh_check, capture_output=True, text=True)
        if result.stdout.strip():
            container_name = candidate
            logger.log(f"Found container: {container_name}")
            break

    if not container_name:
        logger.log_error(f"Container not found for app '{app}'")
        logger.log(f"Tried: {', '.join(container_candidates)}")
        logger.log(f"Run: superdeploy status -p {project}")
        raise SystemExit(1)

    # Build docker exec command with proper TTY handling
    if is_interactive:
        docker_cmd = f"docker exec -it {container_name} {command}"
        ssh_flags = ["-t"]  # Allocate TTY
        logger.log("Interactive mode: TTY enabled")
    else:
        docker_cmd = f"docker exec {container_name} {command}"
        ssh_flags = []
        logger.log("Non-interactive mode")

    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        *ssh_flags,
        f"{ssh_user}@{ssh_host}",
        docker_cmd,
    ]

    try:
        # Use different subprocess call for interactive vs non-interactive
        if is_interactive:
            # Interactive: Don't capture output, let user interact
            result = subprocess.run(ssh_cmd)
        else:
            # Non-interactive: Capture and log
            result = subprocess.run(ssh_cmd, check=True)

        if result.returncode == 0:
            logger.success("Command executed successfully")
            if not verbose and not is_interactive:
                console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    except subprocess.CalledProcessError as e:
        logger.log_error(f"Command failed with exit code {e.returncode}")
        raise SystemExit(e.returncode)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        raise SystemExit(130)
