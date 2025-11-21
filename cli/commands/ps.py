"""
Process Status Command

Show running application containers with replica counts (Heroku-like).
"""

import click
from rich.table import Table

from cli.base import ProjectCommand
import yaml


class ProcessStatusCommand(ProjectCommand):
    def _read_processes_from_marker(self, app_name: str, app_config: dict) -> dict:
        """Read processes from marker file (local path, VM, or GitHub)."""
        processes = {}

        try:
            # Try local path first (if running from code directory)
            app_path = app_config.get("path")
            if app_path:
                from pathlib import Path
                from cli.marker_manager import MarkerManager
                import os

                # Expand ~ and resolve path
                expanded_path = (
                    Path(os.path.expanduser(app_path)).expanduser().resolve()
                )

                # Try original path first
                marker = MarkerManager.load_marker(expanded_path)
                if marker and marker.processes:
                    processes = {
                        name: proc.to_dict() for name, proc in marker.processes.items()
                    }
                    return processes

                # Try alternative paths (common code locations)
                alt_paths = [
                    Path.home() / "Desktop" / "cheapa.io" / "code" / app_name,
                    Path.home() / "code" / app_name,
                    Path("/Users") / os.getenv("USER", "") / "code" / app_name,
                ]

                for alt_path in alt_paths:
                    if alt_path.exists():
                        marker = MarkerManager.load_marker(alt_path)
                        if marker and marker.processes:
                            processes = {
                                name: proc.to_dict()
                                for name, proc in marker.processes.items()
                            }
                            return processes

            # Try VM
            vm_service = self.ensure_vm_service()
            ssh_service = vm_service.get_ssh_service()

            try:
                vm_name, vm_ip = self.get_vm_for_app(app_name)
                marker_path = f"/opt/superdeploy/projects/{self.project_name}/data/{app_name}/superdeploy"

                marker_result = ssh_service.execute_command(
                    vm_ip,
                    f"cat {marker_path} 2>/dev/null || echo ''",
                    timeout=5,
                )

                if marker_result.returncode == 0 and marker_result.stdout.strip():
                    marker_data = yaml.safe_load(marker_result.stdout)
                    if marker_data and "processes" in marker_data:
                        processes = marker_data["processes"]
                        return processes
            except Exception:
                pass

            # Try GitHub if VM failed
            app_repo = app_config.get("repo") or app_name
            app_owner = app_config.get("owner")

            if app_owner:
                try:
                    import os
                    import urllib.request
                    import urllib.error

                    github_token = os.getenv("GITHUB_TOKEN")
                    if github_token:
                        for branch in ["main", "master"]:
                            url = f"https://api.github.com/repos/{app_owner}/{app_repo}/contents/superdeploy?ref={branch}"

                            req = urllib.request.Request(url)
                            req.add_header("Authorization", f"token {github_token}")
                            req.add_header("Accept", "application/vnd.github.v3.raw")

                            try:
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    if response.status == 200:
                                        marker_text = response.read().decode("utf-8")
                                        marker_data = yaml.safe_load(marker_text)

                                        if marker_data and "processes" in marker_data:
                                            processes = marker_data["processes"]
                                            return processes
                            except (urllib.error.HTTPError, Exception):
                                continue
                except Exception:
                    pass

        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to read marker file for {app_name}: {e}")

        return processes

    """Show application process status with replicas."""

    def execute(self) -> None:
        """Execute ps command."""
        # Load config
        config = self.config_service.get_raw_config(self.project_name)
        apps = config.get("apps", {})

        if not apps:
            if self.json_output:
                self.output_json({"project": self.project_name, "apps": [], "total": 0})
                return
            self.console.print("[yellow]No applications configured[/yellow]")
            return

        # JSON output mode
        if self.json_output:
            apps_data = []
            for app_name, app_config in apps.items():
                # Read processes from MARKER FILE (not DB!)
                processes = self._read_processes_from_marker(app_name, app_config)

                # Determine app type and port from processes
                app_port = None
                total_replicas = 0
                for proc_name, proc_config in processes.items():
                    if proc_config.get("port"):
                        app_port = proc_config.get("port")
                    total_replicas += proc_config.get("replicas", 1)

                app_type = app_config.get("type")
                if not app_type:
                    app_type = "web" if app_port else "worker"

                apps_data.append(
                    {
                        "name": app_name,
                        "type": app_type,
                        "replicas": total_replicas if total_replicas > 0 else 1,
                        "port": app_port,
                        "vm": app_config.get("vm", "app"),
                        "status": "configured",  # TODO: Check actual Docker container status
                        "processes": processes,  # Process definitions from marker file
                    }
                )

            total_replicas = sum(app.get("replicas", 1) for app in apps.values())
            self.output_json(
                {
                    "project": self.project_name,
                    "apps": apps_data,
                    "total_apps": len(apps),
                    "total_replicas": total_replicas,
                }
            )
            return

        self.show_header(
            title="Application Processes",
            project=self.project_name,
            subtitle="Running containers and replicas",
        )

        # Create table
        table = Table(
            show_header=True,
            header_style="bold cyan",
            title=f"{self.project_name} processes",
        )
        table.add_column("App", style="cyan", no_wrap=True)
        table.add_column("Type", style="white")
        table.add_column("Replicas", style="yellow", justify="center")
        table.add_column("Port", style="green", justify="center")
        table.add_column("VM", style="magenta")
        table.add_column("Status", style="blue")

        for app_name, app_config in apps.items():
            # Determine app type (auto-detect if not specified)
            app_type = app_config.get("type")
            if not app_type:
                app_type = "web" if app_config.get("port") else "worker"

            # Get replicas
            replicas = app_config.get("replicas", 1)

            # Get port
            port = str(app_config.get("port", "-"))

            # Get VM
            vm = app_config.get("vm", "app")

            # Get status (placeholder - would need SSH to VM to check actual status)
            status = "configured"  # TODO: Check actual Docker container status

            table.add_row(app_name, app_type, str(replicas), port, vm, status)

        self.console.print(table)

        # Summary
        total_replicas = sum(app.get("replicas", 1) for app in apps.values())
        self.console.print(
            f"\n[dim]Total apps: {len(apps)} | Total replicas: {total_replicas}[/dim]"
        )

        # Show scaling examples
        self.console.print("\n[bold]Scale commands:[/bold]")
        if apps:
            first_app = list(apps.keys())[0]
            self.console.print(
                f"  [cyan]superdeploy {self.project_name}:scale {first_app}=3[/cyan]"
            )


@click.command(name="ps")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def ps(project, verbose, json_output):
    """
    Show application processes and replicas (Heroku-like)

    Displays all configured applications with their type, replica count,
    port, and deployment status.

    Examples:
        superdeploy cheapa:ps
        superdeploy myproject:ps -v
    """
    cmd = ProcessStatusCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()
