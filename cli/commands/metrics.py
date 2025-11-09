"""SuperDeploy CLI - Metrics command"""

import click
from rich.table import Table
from cli.base import ProjectCommand
from cli.utils import validate_env_vars, ssh_command


class MetricsCommand(ProjectCommand):
    """Show deployment metrics and statistics."""

    def __init__(self, project_name: str, days: int = 7, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.days = days

    def execute(self) -> None:
        """Execute metrics command."""
        # Load state to get VM IPs
        state = self.state_service.load_state()

        if not state or "vms" not in state:
            self.console.print("[red]✗[/red] No deployment state found")
            self.console.print(f"Run: [red]superdeploy {self.project_name}:up[/red]")
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

        self.show_header(
            title="Deployment Metrics",
            project=self.project_name,
            details={"Period": f"Last {self.days} days"},
        )

        # Get container stats
        try:
            stats_output = ssh_command(
                host=env["CORE_EXTERNAL_IP"],
                user=env.get("SSH_USER", "superdeploy"),
                key_path=env["SSH_KEY_PATH"],
                cmd=f"docker stats --no-stream --format 'table {{{{.Name}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}\\t{{{{.NetIO}}}}' | grep {self.project_name}",
            )

            # Parse and display stats
            self.console.print("\n[bold]Current Resource Usage:[/bold]\n")

            table = Table(title="Resource Usage", title_justify="left", padding=(0, 1))
            table.add_column("Service", style="cyan")
            table.add_column("CPU %", style="yellow")
            table.add_column("Memory", style="green")
            table.add_column("Network I/O", style="blue")

            for line in stats_output.strip().split("\n"):
                if line and self.project_name in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        service = parts[0].replace(f"{self.project_name}-", "")
                        cpu = parts[1]
                        mem = f"{parts[2]} / {parts[3]}"
                        net = parts[4] if len(parts) > 4 else "N/A"
                        table.add_row(service, cpu, mem, net)

            self.console.print(table)

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️  Could not fetch resource stats: {e}[/yellow]"
            )

        # Get container uptime
        try:
            uptime_output = ssh_command(
                host=env["CORE_EXTERNAL_IP"],
                user=env.get("SSH_USER", "superdeploy"),
                key_path=env["SSH_KEY_PATH"],
                cmd=f"docker ps --filter name={self.project_name} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
            )

            self.console.print("\n[bold]Service Uptime:[/bold]\n")

            table = Table(title="Service Uptime", title_justify="left", padding=(0, 1))
            table.add_column("Service", style="cyan")
            table.add_column("Status", style="green")

            for line in uptime_output.strip().split("\n")[1:]:  # Skip header
                if line and self.project_name in line:
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        service = parts[0].replace(f"{self.project_name}-", "")
                        status = parts[1]
                        table.add_row(service, status)

            self.console.print(table)

        except Exception as e:
            self.console.print(f"[yellow]⚠️  Could not fetch uptime: {e}[/yellow]")

        # Deployment history (from container labels)
        try:
            history_output = ssh_command(
                host=env["CORE_EXTERNAL_IP"],
                user=env.get("SSH_USER", "superdeploy"),
                key_path=env["SSH_KEY_PATH"],
                cmd=f"docker inspect $(docker ps -q --filter name={self.project_name}) --format '{{{{.Name}}}} {{{{.Config.Labels}}}}' 2>/dev/null | grep git.sha",
            )

            if history_output.strip():
                self.console.print("\n[bold]Recent Deployments:[/bold]\n")

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
                        service = parts[0].replace(f"/{self.project_name}-", "")

                        # Extract SHA and ref from labels
                        sha = "N/A"
                        ref = "N/A"

                        if "com.superdeploy.git.sha:" in line:
                            sha = line.split("com.superdeploy.git.sha:")[1].split()[0]
                        if "com.superdeploy.git.ref:" in line:
                            ref = line.split("com.superdeploy.git.ref:")[1].split()[0]

                        table.add_row(service, sha[:7], ref)

                self.console.print(table)

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️  Could not fetch deployment history: {e}[/yellow]"
            )

        # Summary
        self.console.print(
            "\n[dim]For detailed logs: superdeploy logs -a <service>[/dim]"
        )


@click.command()
@click.option("--days", "-d", default=7, help="Number of days to analyze")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def metrics(project, days, verbose):
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
    cmd = MetricsCommand(project, days=days, verbose=verbose)
    cmd.run()
