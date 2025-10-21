import os

"""SuperDeploy CLI - Run command"""

import click
import subprocess
from rich.console import Console
from cli.utils import load_env, validate_env_vars

console = Console()


@click.command(name="run")
@click.option("--project", "-p", required=True, help="Project name")
@click.argument("app")
@click.argument("command")
def run(project, app, command):
    """
    Run one-off command in app container

    \b
    Examples:
      superdeploy run api "python manage.py migrate"
      superdeploy run api "bash"
      superdeploy run dashboard "npm install"
    """
    env = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    console.print(f"[cyan]⚡ Running command in [bold]{app}[/bold]:[/cyan]")
    console.print(f"[dim]$ {command}[/dim]\n")

    # SSH + docker exec (container naming: {project}-{app})
    ssh_key = os.path.expanduser(env["SSH_KEY_PATH"])
    ssh_user = env.get("SSH_USER", "superdeploy")
    ssh_host = env["CORE_EXTERNAL_IP"]

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
            console.print("\n[green]✅ Command executed successfully![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Command failed with exit code {e.returncode}[/red]")
        raise SystemExit(e.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Interrupted[/yellow]")
        raise SystemExit(130)
