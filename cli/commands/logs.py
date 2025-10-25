import os

"""SuperDeploy CLI - Logs command"""

import click
import subprocess
from rich.console import Console
from cli.utils import load_env, validate_env_vars

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-f", "--follow", is_flag=True, help="Follow logs (tail -f)")
@click.option("-n", "--lines", default=100, help="Number of lines")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def logs(project, app, follow, lines, environment):
    """
    View application logs

    \b
    Examples:
      superdeploy logs -a api              # Last 100 lines
      superdeploy logs -a api -f           # Follow logs
      superdeploy logs -a api -n 500       # Last 500 lines
    """
    env = load_env(project)

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    console.print(f"[cyan]📋 Fetching logs for [bold]{project}/{app}[/bold]...[/cyan]")

    # SSH command to get docker logs
    ssh_key = os.path.expanduser(env["SSH_KEY_PATH"])
    ssh_user = env.get("SSH_USER", "superdeploy")
    ssh_host = env["CORE_EXTERNAL_IP"]

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

    try:
        # Stream logs to terminal
        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        console.print(f"[green]✅ Streaming logs from {app}...[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        for line in process.stdout:
            print(line, end="")

        process.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Stopped[/yellow]")
        process.terminate()
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to fetch logs: {e}[/red]")
        raise SystemExit(1)
