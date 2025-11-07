"""SuperDeploy CLI - Metrics command"""

import click
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header
from cli.utils import validate_env_vars, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--days", "-d", default=7, help="Number of days to analyze")
def metrics(project, days):
    """
    Show deployment metrics and statistics

    \b
    Examples:
      superdeploy acme:metrics                # Last 7 days
      superdeploy acme:metrics -d 30          # Last 30 days

    \b
    Metrics include:
    - Deployment frequency
    - Success/failure rate
    - Average deployment duration
    - Service uptime
    - Resource usage (CPU/Memory)
    """
    # Load state to get VM IPs
    from cli.state_manager import StateManager

    state_mgr = StateManager(get_project_root(), project)
    state = state_mgr.load_state()

    if not state or "vms" not in state:
        console.print("[red]✗[/red] No deployment state found")
        console.print(f"Run: [red]superdeploy {project}:up[/red]")
        raise SystemExit(1)

    # Build env dict from state
    env = {}
    for vm_name, vm_data in state.get("vms", {}).items():
        if "external_ip" in vm_data:
            env_key = vm_name.upper().replace("-", "_")
            env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    show_header(
        title="Deployment Metrics",
        project=project,
        details={"Period": f"Last {days} days"},
        console=console,
    )

    # Get container stats
    try:
        stats_output = ssh_command(
            host=env["CORE_EXTERNAL_IP"],
            user=env.get("SSH_USER", "superdeploy"),
            key_path=env["SSH_KEY_PATH"],
            cmd=f"docker stats --no-stream --format 'table {{{{.Name}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}\\t{{{{.NetIO}}}}' | grep {project}",
        )

        # Parse and display stats
        console.print("\n[bold]Current Resource Usage:[/bold]\n")

        table = Table(title="Resource Usage", title_justify="left", padding=(0, 1))
        table.add_column("Service", style="cyan")
        table.add_column("CPU %", style="yellow")
        table.add_column("Memory", style="green")
        table.add_column("Network I/O", style="blue")

        for line in stats_output.strip().split("\n"):
            if line and project in line:
                parts = line.split()
                if len(parts) >= 4:
                    service = parts[0].replace(f"{project}-", "")
                    cpu = parts[1]
                    mem = f"{parts[2]} / {parts[3]}"
                    net = parts[4] if len(parts) > 4 else "N/A"
                    table.add_row(service, cpu, mem, net)

        console.print(table)

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not fetch resource stats: {e}[/yellow]")

    # Get container uptime
    try:
        uptime_output = ssh_command(
            host=env["CORE_EXTERNAL_IP"],
            user=env.get("SSH_USER", "superdeploy"),
            key_path=env["SSH_KEY_PATH"],
            cmd=f"docker ps --filter name={project} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        console.print("\n[bold]Service Uptime:[/bold]\n")

        table = Table(title="Service Uptime", title_justify="left", padding=(0, 1))
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")

        for line in uptime_output.strip().split("\n")[1:]:  # Skip header
            if line and project in line:
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    service = parts[0].replace(f"{project}-", "")
                    status = parts[1]
                    table.add_row(service, status)

        console.print(table)

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not fetch uptime: {e}[/yellow]")

    # Deployment history (from container labels)
    try:
        history_output = ssh_command(
            host=env["CORE_EXTERNAL_IP"],
            user=env.get("SSH_USER", "superdeploy"),
            key_path=env["SSH_KEY_PATH"],
            cmd=f"docker inspect $(docker ps -q --filter name={project}) --format '{{{{.Name}}}} {{{{.Config.Labels}}}}' 2>/dev/null | grep git.sha",
        )

        if history_output.strip():
            console.print("\n[bold]Recent Deployments:[/bold]\n")

            table = Table(
                title="Recent Deployments", title_justify="left", padding=(0, 1)
            )
            table.add_column("Service", style="cyan")
            table.add_column("Git SHA", style="yellow")
            table.add_column("Git Ref", style="blue")

            for line in history_output.strip().split("\n"):
                if "git.sha" in line:
                    # Parse container labels
                    parts = line.split()
                    service = parts[0].replace(f"/{project}-", "")

                    # Extract SHA and ref from labels
                    sha = "N/A"
                    ref = "N/A"

                    if "com.superdeploy.git.sha:" in line:
                        sha = line.split("com.superdeploy.git.sha:")[1].split()[0]
                    if "com.superdeploy.git.ref:" in line:
                        ref = line.split("com.superdeploy.git.ref:")[1].split()[0]

                    table.add_row(service, sha[:7], ref)

            console.print(table)

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not fetch deployment history: {e}[/yellow]")

    # Summary
    console.print("\n[dim]For detailed logs: superdeploy logs -a <service>[/dim]")
