"""SuperDeploy CLI - Switch between releases"""

import click
import os
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from cli.base import ProjectCommand
from cli.utils import ssh_command


class SwitchCommand(ProjectCommand):
    """Switch between any release version (forward or backward)."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        version: str = None,
        force: bool = False,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.version = version
        self.force = force

    def execute(self) -> None:
        """Execute switch command."""
        self.show_header(
            title="Release Rollback",
            project=self.project_name,
            app=self.app_name,
            details={"Version": self.version if self.version else "Interactive"},
        )

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
                self.console.print(
                    f"[red]❌ VM IP not found in state: {ip_key}[/red]"
                )
                return

            ssh_host = env[ip_key]
            ssh_key = os.path.expanduser(ssh_key_path)

        except Exception as e:
            self.console.print(f"[red]❌ Error: {e}[/red]")
            return

        # List available releases
        self.console.print(
            f"[cyan]📋 Fetching releases for {self.app_name}...[/cyan]\n"
        )

        list_cmd = f"ls -t /opt/apps/{self.project_name}/releases/{self.app_name}/ 2>/dev/null || echo 'NO_RELEASES'"

        try:
            releases_output = ssh_command(
                host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
            )

            if releases_output.strip() == "NO_RELEASES":
                self.console.print(f"[red]❌ No releases found for {self.app_name}[/red]")
                self.console.print(
                    "[dim]Deploy the app first: git push origin production[/dim]"
                )
                return

            releases = [
                r.strip() for r in releases_output.strip().split("\n") if r.strip()
            ]

            if not releases:
                self.console.print("[red]❌ No releases found[/red]")
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
                title=f"Available Releases - {self.app_name.upper()}",
                show_header=True,
                title_justify="left",
                padding=(0, 1),
            )
            table.add_column("#", style="cyan", width=4)
            table.add_column("Release", style="green")
            table.add_column("SHA", style="yellow", width=10)
            table.add_column("Status", style="bold", width=12)

            for idx, release in enumerate(releases[:10], 1):
                parts = release.split("_")
                timestamp = parts[0] if len(parts) > 0 else "unknown"
                sha = parts[-1] if len(parts) > 1 else "unknown"

                # Format timestamp
                if len(timestamp) == 15:  # YYYYMMDD_HHMMSS
                    formatted_time = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}"
                else:
                    formatted_time = timestamp

                status = "✅ CURRENT" if release == current_name else ""

                table.add_row(str(idx), formatted_time, sha, status)

            self.console.print(table)
            self.console.print()

            # Determine target release
            target_release = None

            if not self.version:
                # Interactive mode - ask user to select
                if self.force:
                    self.console.print(
                        "[yellow]⚠️  --force requires --version/-v[/yellow]"
                    )
                    return

                self.console.print("[bold]Select a release to switch to:[/bold]")
                choice = Prompt.ask(
                    "Enter release number (1-{}) or 'q' to quit".format(len(releases)),
                    default="q",
                )

                if choice.lower() == "q":
                    self.console.print("[yellow]⏹️  Cancelled[/yellow]")
                    return

                try:
                    idx = int(choice)
                    if 1 <= idx <= len(releases):
                        target_release = releases[idx - 1]
                    else:
                        self.console.print(f"[red]❌ Invalid selection: {choice}[/red]")
                        return
                except ValueError:
                    self.console.print(f"[red]❌ Invalid input: {choice}[/red]")
                    return

            elif self.version == "previous":
                # Switch to previous (second in list)
                if len(releases) < 2:
                    self.console.print("[red]❌ No previous release available[/red]")
                    return
                target_release = releases[1]

            elif self.version.isdigit():
                # Index-based selection
                idx = int(self.version)
                if 1 <= idx <= len(releases):
                    target_release = releases[idx - 1]
                else:
                    self.console.print(
                        f"[red]❌ Invalid index: {self.version} (available: 1-{len(releases)})[/red]"
                    )
                    return

            else:
                # Find matching release by name/sha
                for r in releases:
                    if self.version in r:
                        target_release = r
                        break

                if not target_release:
                    self.console.print(
                        f"[red]❌ Release not found: {self.version}[/red]"
                    )
                    return

            # Check if already current
            if target_release == current_name:
                self.console.print(
                    f"[yellow]⚠️  Already running: {target_release}[/yellow]"
                )
                return

            # Show confirmation
            self.console.print(
                Panel(
                    f"[cyan]🔄 Switch Release (Zero-Downtime)[/cyan]\n\n"
                    f"[white]App:[/white] {self.app_name}\n"
                    f"[white]From:[/white] {current_name or 'unknown'}\n"
                    f"[white]To:[/white] {target_release}\n\n"
                    f"[dim]New container will start before old one stops[/dim]\n"
                    f"[dim]Health check will verify new version before switching[/dim]\n"
                    f"[dim]Automatic rollback if health check fails[/dim]",
                    border_style="cyan",
                )
            )

            # Confirm
            if not self.force:
                self.console.print(
                    "Continue with switch? "
                    "[bold bright_white]\\[y/n][/bold bright_white] [dim](y)[/dim]: ",
                    end="",
                )
                answer = input().strip().lower()
                if answer not in ["y", "yes", ""]:  # Empty = default yes
                    self.console.print("[yellow]⏹️  Switch cancelled[/yellow]")
                    return

            self.console.print()  # Add 1 newline after confirmation
            # Execute switch with zero-downtime
            self.console.print("[cyan]🔄 Switching release (zero-downtime)...[/cyan]")

            switch_cmd = f"""
            set -e
            cd /opt/apps/{self.project_name}/releases/{self.app_name}/{target_release}
            
            CONTAINER_NAME="{self.project_name}-{self.app_name}"
            NEW_CONTAINER="${{CONTAINER_NAME}}-new-$RANDOM"
            
            echo "📦 Preparing new release..."
            
            # Note: .env no longer used in new releases (secrets via docker compose env_file or runtime injection)
            
            # Temporarily rename service in compose file to avoid name conflict
            sed "s/container_name: $CONTAINER_NAME/container_name: $NEW_CONTAINER/" docker-compose-{self.app_name}.yml > /tmp/docker-compose-new.yml
            
            echo "🐳 Starting new container: $NEW_CONTAINER"
            docker compose -f /tmp/docker-compose-new.yml up -d --wait
            
            # Wait for container to be ready
            echo "⏳ Waiting for health check..."
            sleep 3
            
            # Check if new container is running
            if docker ps --filter "name=$NEW_CONTAINER" --format "{{{{.Names}}}}" | grep -q "$NEW_CONTAINER"; then
                echo "✅ New container is running"
                
                # Wait for health check (if defined)
                sleep 2
                HEALTH_STATUS=$(docker inspect --format='{{{{.State.Health.Status}}}}' $NEW_CONTAINER 2>/dev/null || echo "none")
                
                if [ "$HEALTH_STATUS" = "healthy" ] || [ "$HEALTH_STATUS" = "none" ]; then
                    echo "✅ Health check passed (status: $HEALTH_STATUS)"
                    
                    # Stop and remove old container
                    if docker ps -a --filter "name=$CONTAINER_NAME" --format "{{{{.Names}}}}" | grep -q "^$CONTAINER_NAME$"; then
                        echo "⏸️  Stopping old container..."
                        docker stop $CONTAINER_NAME 2>/dev/null || true
                        docker rm $CONTAINER_NAME 2>/dev/null || true
                    fi
                    
                    # Rename new container to proper name
                    echo "🔄 Switching to new container..."
                    docker rename $NEW_CONTAINER $CONTAINER_NAME
                    
                    # Update symlink (atomic operation)
                    ln -sfn /opt/apps/{self.project_name}/releases/{self.app_name}/{target_release} /opt/apps/{self.project_name}/current/{self.app_name}
                    
                    echo "✅ Zero-downtime switch complete!"
                    echo "SWITCH_SUCCESS"
                else
                    echo "❌ Health check failed (status: $HEALTH_STATUS)"
                    echo "🔙 Rolling back..."
                    docker stop $NEW_CONTAINER 2>/dev/null || true
                    docker rm $NEW_CONTAINER 2>/dev/null || true
                    echo "SWITCH_FAILED"
                    exit 1
                fi
            else
                echo "❌ New container failed to start"
                docker stop $NEW_CONTAINER 2>/dev/null || true
                docker rm $NEW_CONTAINER 2>/dev/null || true
                echo "SWITCH_FAILED"
                exit 1
            fi
            
            # Cleanup
            rm -f /tmp/docker-compose-new.yml
            """

            result = ssh_command(
                host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=switch_cmd
            )

            if "SWITCH_SUCCESS" in result:
                self.console.print("\n[green]✅ Zero-downtime switch completed![/green]")
                self.console.print(f"[green]✅ Now running: {target_release}[/green]")
                self.console.print("[dim]  → New container started[/dim]")
                self.console.print("[dim]  → Health check passed[/dim]")
                self.console.print("[dim]  → Old container removed[/dim]")

                # Show quick verification command
                app_port = apps[self.app_name].get("port", 8000)
                self.console.print(
                    f"\n[dim]Verify: curl http://{ssh_host}:{app_port}/[/dim]"
                )
            elif "SWITCH_FAILED" in result:
                self.console.print("\n[red]❌ Switch failed - rollback performed[/red]")
                self.console.print(
                    "[yellow]⚠️  Old version is still running (no downtime)[/yellow]"
                )
                self.console.print(f"\n[dim]{result}[/dim]")
                raise SystemExit(1)
            else:
                self.console.print("[red]❌ Switch failed[/red]")
                self.console.print(f"[dim]{result}[/dim]")
                raise SystemExit(1)

        except Exception as e:
            self.console.print(f"[red]❌ Switch failed: {e}[/red]")
            import traceback

            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            raise SystemExit(1)


@click.command(name="releases:rollback")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option(
    "--version",
    "-v",
    help="Release version (timestamp_sha, index number, or 'previous')",
)
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.option("--verbose", is_flag=True, help="Show all command output")
def releases_rollback(project, app, version, force, verbose):
    """
    Switch between any release version (forward or backward)

    \b
    Examples:
      superdeploy cheapa:releases:rollback -a api                           # Interactive: show list and select
      superdeploy cheapa:releases:rollback -a api -v 2                      # Switch to release #2
      superdeploy cheapa:releases:rollback -a api -v 20251030_143312_3a4a89d  # Switch to specific release
      superdeploy cheapa:releases:rollback -a api -v previous               # Switch to previous release

    \b
    Features:
    - Navigate forward/backward between any releases
    - Interactive selection if no version specified
    - TRUE zero-downtime switching (new starts before old stops)
    - Automatic health checks and rollback on failure
    - Keeps last 5 releases for instant switching
    """
    cmd = SwitchCommand(project, app, version=version, force=force, verbose=verbose)
    cmd.run()


if __name__ == "__main__":
    releases_rollback()
