import os

"""SuperDeploy CLI - Scale command"""

import click
from rich.console import Console
from cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.argument("scale_spec")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def scale(project, scale_spec, environment):
    """
    Scale service replicas

    \b
    Examples:
      superdeploy scale api=3        # Scale API to 3 replicas
      superdeploy scale dashboard=5  # Scale Dashboard to 5

    \b
    Note: Uses docker-compose scale command
    """
    env_vars = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env_vars, required):
        raise SystemExit(1)

    # Parse scale spec
    try:
        app, replicas = scale_spec.split("=")
        replicas = int(replicas)
    except ValueError:
        console.print("[red]❌ Invalid format! Use: app=replicas (e.g., api=3)[/red]")
        raise SystemExit(1)

    console.print(
        f"[cyan]📊 Scaling [bold]{app}[/bold] to [bold]{replicas}[/bold] replicas...[/cyan]"
    )

    # SSH command
    ssh_host = env_vars["CORE_EXTERNAL_IP"]
    ssh_user = env_vars.get("SSH_USER", "superdeploy")
    ssh_key = os.path.expanduser(env_vars["SSH_KEY_PATH"])

    # Project-specific compose directory
    scale_cmd = f"cd /opt/superdeploy/projects/{project}/compose && docker compose -f docker-compose.apps.yml up -d --scale {app}={replicas} --no-recreate"

    try:
        result = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=scale_cmd
        )

        console.print(f"[green]✅ Scaling {project}/{app} complete![/green]")
        console.print(f"\n[dim]{result}[/dim]")

        # Show current status (container naming: {project}-{app})
        status_cmd = f"docker ps --filter name={project}-{app} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'"
        status = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=status_cmd
        )

        console.print("\n[cyan]Current status:[/cyan]")
        console.print(status)

    except Exception as e:
        console.print(f"[red]❌ Scaling failed: {e}[/red]")
        raise SystemExit(1)
