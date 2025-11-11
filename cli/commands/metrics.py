"""SuperDeploy CLI - Metrics command"""

import click
from rich.table import Table
from cli.base import ProjectCommand


class MetricsCommand(ProjectCommand):
    """Show deployment metrics and statistics."""

    def __init__(self, project_name: str, days: int = 7, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.days = days

    def execute(self) -> None:
        """Execute metrics command."""
        # Require deployment
        self.require_deployment()

        self.show_header(
            title="Deployment Metrics",
            project=self.project_name,
            details={"Period": f"Last {self.days} days"},
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, "metrics")

        logger.step("Collecting metrics")

        # Get VM and SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()
        vm_ip = self.state_service.get_vm_ip_by_role("core", index=0)

        # Display all metrics
        self._show_resource_usage(vm_ip, ssh_service)
        self._show_service_uptime(vm_ip, ssh_service)
        self._show_deployment_history(vm_ip, ssh_service)

        logger.success("Metrics collected successfully")

        # Summary
        self.console.print(
            "\n[dim]For detailed logs: superdeploy logs -a <service>[/dim]"
        )

        if not self.verbose:
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _show_resource_usage(self, vm_ip: str, ssh_service) -> None:
        """Show current resource usage."""
        try:
            cmd = f"docker stats --no-stream --format 'table {{{{.Name}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}\\t{{{{.NetIO}}}}' | grep {self.project_name}"
            result = ssh_service.execute_command(vm_ip, cmd, timeout=30)

            self.console.print("\n[bold]Current Resource Usage:[/bold]\n")

            table = Table(title="Resource Usage", title_justify="left", padding=(0, 1))
            table.add_column("Service", style="cyan")
            table.add_column("CPU %", style="yellow")
            table.add_column("Memory", style="green")
            table.add_column("Network I/O", style="blue")

            for line in result.stdout.strip().split("\n"):
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

    def _show_service_uptime(self, vm_ip: str, ssh_service) -> None:
        """Show service uptime."""
        try:
            cmd = f"docker ps --filter name={self.project_name} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'"
            result = ssh_service.execute_command(vm_ip, cmd, timeout=30)

            self.console.print("\n[bold]Service Uptime:[/bold]\n")

            table = Table(title="Service Uptime", title_justify="left", padding=(0, 1))
            table.add_column("Service", style="cyan")
            table.add_column("Status", style="green")

            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                if line and self.project_name in line:
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        service = parts[0].replace(f"{self.project_name}-", "")
                        status = parts[1]
                        table.add_row(service, status)

            self.console.print(table)

        except Exception as e:
            self.console.print(f"[yellow]⚠️  Could not fetch uptime: {e}[/yellow]")

    def _show_deployment_history(self, vm_ip: str, ssh_service) -> None:
        """Show deployment history from container labels."""
        try:
            cmd = f"docker inspect $(docker ps -q --filter name={self.project_name}) --format '{{{{.Name}}}} {{{{.Config.Labels}}}}' 2>/dev/null | grep git.sha"
            result = ssh_service.execute_command(vm_ip, cmd, timeout=30, check=False)

            if result.stdout.strip():
                self.console.print("\n[bold]Recent Deployments:[/bold]\n")

                table = Table(
                    title="Recent Deployments", title_justify="left", padding=(0, 1)
                )
                table.add_column("Service", style="cyan")
                table.add_column("Git SHA", style="yellow")
                table.add_column("Git Ref", style="blue")

                for line in result.stdout.strip().split("\n"):
                    if "git.sha" in line:
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
