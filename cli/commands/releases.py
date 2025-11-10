"""SuperDeploy CLI - Releases command"""

import click
import os
from rich.table import Table
from cli.base import ProjectCommand
from cli.utils import ssh_command


class ReleasesCommand(ProjectCommand):
    """Show release history for an app (last 5 releases kept)."""

    def __init__(
        self, project_name: str, app_name: str, limit: int = 10, verbose: bool = False
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.limit = limit

    def execute(self) -> None:
        """Execute releases command."""
        self.show_header(
            title="Release History",
            project=self.project_name,
            app=self.app_name,
            details={"Limit": str(self.limit)},
        )

        # Check if state service is available
        if not self.state_service:
            self.console.print("[yellow]⚠️  Release history not available[/yellow]\n")
            self.console.print(
                "[dim]This project uses version tracking instead of release history.[/dim]"
            )
            self.console.print(
                f"[dim]Use: [cyan]superdeploy {self.project_name}:status[/cyan] to see deployed versions[/dim]\n"
            )
            return

        # Load project config to find VM
        try:
            config = self.config_service.get_raw_config(self.project_name)
            apps = config.get("apps", {})

            if self.app_name not in apps:
                self.console.print(
                    f"[red]❌ App '{self.app_name}' not found in project config[/red]"
                )
                return

            vm_role = apps[self.app_name].get("vm", "core")

            # Get SSH config from project config
            ssh_config = config.get("cloud", {}).get("ssh", {})
            ssh_key_path = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
            ssh_user = ssh_config.get("user", "superdeploy")

            # Get VM IP from state
            state = self.state_service.load_state()

            if not state or "vms" not in state:
                self.console.print("[red]✗[/red] No deployment state found")
                return

            # Build env dict from state
            env = {}
            for vm_name, vm_data in state.get("vms", {}).items():
                if "external_ip" in vm_data:
                    env_key = vm_name.upper().replace("-", "_")
                    env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

            ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
            if ip_key not in env:
                self.console.print(f"[red]❌ VM IP not found in state: {ip_key}[/red]")
                return

            ssh_host = env[ip_key]
            ssh_key = os.path.expanduser(ssh_key_path)

        except Exception as e:
            self.console.print(f"[red]❌ Error: {e}[/red]")
            return

        self.console.print(
            f"[cyan]📋 Fetching release history for [bold]{self.app_name}[/bold]...[/cyan]"
        )

        # List releases from filesystem
        list_cmd = f"ls -t /opt/apps/{self.project_name}/releases/{self.app_name}/ 2>/dev/null || echo 'NO_RELEASES'"

        try:
            releases_output = ssh_command(
                host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
            )

            if releases_output.strip() == "NO_RELEASES":
                self.console.print(
                    f"[yellow]⚠️  No releases found for {self.app_name}[/yellow]"
                )
                self.console.print(
                    "[dim]Deploy the app first: git push origin production[/dim]"
                )
                return

            releases_list = [
                r.strip() for r in releases_output.strip().split("\n") if r.strip()
            ]

            if not releases_list:
                self.console.print("[yellow]⚠️  No releases found[/yellow]")
                return

            # Get current release
            current_cmd = f"readlink /opt/apps/{self.project_name}/current/{self.app_name} 2>/dev/null || echo 'NONE'"
            current_release = ssh_command(
                host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
            ).strip()

            current_name = (
                current_release.split("/")[-1] if current_release != "NONE" else None
            )

            # Build table
            table = Table(
                title=f"Release History - {self.app_name.upper()}",
                show_header=True,
                title_justify="left",
                padding=(0, 1),
            )
            table.add_column("#", style="cyan", no_wrap=True)
            table.add_column("Timestamp", style="green")
            table.add_column("Git SHA", style="yellow")
            table.add_column("Status", style="bold")

            for idx, release in enumerate(releases_list[: self.limit], 1):
                parts = release.split("_")
                timestamp = parts[0] if len(parts) > 0 else "unknown"
                sha = parts[-1] if len(parts) > 1 else "unknown"

                # Format timestamp
                if len(timestamp) == 15:  # YYYYMMDD_HHMMSS
                    formatted_time = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
                else:
                    formatted_time = timestamp

                if release == current_name:
                    status = "✅ CURRENT"
                elif idx == 2 and current_name:
                    status = "⏮️  PREVIOUS"
                else:
                    status = ""

                table.add_row(str(idx), formatted_time, sha, status)

            self.console.print("\n")
            self.console.print(table)

            # Show switch hints
            self.console.print("\n[bold]Quick Commands:[/bold]")
            self.console.print(
                f"  Switch to any version: [cyan]superdeploy {self.project_name}:switch -a {self.app_name}[/cyan]"
            )
            if len(releases_list) > 1:
                self.console.print(
                    f"  Switch to specific: [cyan]superdeploy {self.project_name}:switch -a {self.app_name} -v 2[/cyan]"
                )
            self.console.print(
                "\n[dim]💡 System keeps last 5 releases for instant switching[/dim]"
            )

        except Exception as e:
            self.console.print(f"[red]❌ Failed to fetch releases: {e}[/red]")
            raise SystemExit(1)


@click.command(name="releases:list")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-n", "--limit", default=10, help="Number of releases to show")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def releases_list(project, app, limit, verbose):
    """
    Show release history for an app (last 5 releases kept)

    \b
    Examples:
      superdeploy cheapa:releases:list -a api          # Show all releases
      superdeploy cheapa:releases:list -a api -n 3     # Show last 3

    \b
    Shows:
    - Release timestamp
    - Git SHA
    - Current/Previous status
    - Use 'superdeploy releases:rollback' to change versions
    """
    cmd = ReleasesCommand(project, app, limit=limit, verbose=verbose)
    cmd.run()
