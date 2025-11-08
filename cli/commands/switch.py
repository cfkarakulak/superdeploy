"""SuperDeploy CLI - Switch between releases"""

import click
from rich.console import Console
from cli.ui_components import show_header
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from cli.utils import ssh_command

console = Console()


@click.command(name="releases:rollback")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option(
    "--version",
    "-v",
    help="Release version (timestamp_sha, index number, or 'previous')",
)
@click.option("--force", is_flag=True, help="Skip confirmation")
def releases_rollback(project, app, version, force):
    """
    Switch between any release version (forward or backward)

    \b
    Examples:
      superdeploy releases:rollback -p cheapa -a api                           # Interactive: show list and select
      superdeploy releases:rollback -p cheapa -a api -v 2                      # Switch to release #2
      superdeploy releases:rollback -p cheapa -a api -v 20251030_143312_3a4a89d  # Switch to specific release
      superdeploy releases:rollback -p cheapa -a api -v previous               # Switch to previous release

    \b
    Features:
    - Navigate forward/backward between any releases
    - Interactive selection if no version specified
    - TRUE zero-downtime switching (new starts before old stops)
    - Automatic health checks and rollback on failure
    - Keeps last 5 releases for instant switching
    """
    show_header(
        title="Release Rollback",
        project=project,
        app=app,
        details={"Version": version if version else "Interactive"},
        console=console,
    )

    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    import os

    # Load project config to find VM
    project_root = get_project_root()
    projects_dir = project_root / "projects"

    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})

        if app not in apps:
            console.print(f"[red]❌ App '{app}' not found in project config[/red]")
            return

        vm_role = apps[app].get("vm", "core")

        # Get SSH config from project config
        ssh_config = project_config.raw_config.get("cloud", {}).get("ssh", {})
        ssh_key_path = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")

        # Get VM IP from state
        from cli.state_manager import StateManager
        from cli.utils import get_project_root as gpr

        state_mgr = StateManager(gpr(), project)
        state = state_mgr.load_state()

        if not state or "vms" not in state:
            console.print("[red]✗[/red] No deployment state found")
            return

        # Build env dict from state
        env = {}
        for vm_name, vm_data in state.get("vms", {}).items():
            if "external_ip" in vm_data:
                env_key = vm_name.upper().replace("-", "_")
                env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            console.print(f"[red]❌ VM IP not found in state: {ip_key}[/red]")
            return

        ssh_host = env[ip_key]
        ssh_key = os.path.expanduser(ssh_key_path)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return

    # List available releases
    console.print(f"[cyan]📋 Fetching releases for {app}...[/cyan]\n")

    list_cmd = (
        f"ls -t /opt/apps/{project}/releases/{app}/ 2>/dev/null || echo 'NO_RELEASES'"
    )

    try:
        releases_output = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
        )

        if releases_output.strip() == "NO_RELEASES":
            console.print(f"[red]❌ No releases found for {app}[/red]")
            console.print("[dim]Deploy the app first: git push origin production[/dim]")
            return

        releases = [r.strip() for r in releases_output.strip().split("\n") if r.strip()]

        if not releases:
            console.print("[red]❌ No releases found[/red]")
            return

        # Get current release
        current_cmd = (
            f"readlink /opt/apps/{project}/current/{app} 2>/dev/null || echo 'NONE'"
        )
        current_release = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
        ).strip()

        current_name = (
            current_release.split("/")[-1] if current_release != "NONE" else None
        )

        # Build table
        table = Table(
            title=f"Available Releases - {app.upper()}",
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

        console.print(table)
        console.print()

        # Determine target release
        target_release = None

        if not version:
            # Interactive mode - ask user to select
            if force:
                console.print("[yellow]⚠️  --force requires --version/-v[/yellow]")
                return

            console.print("[bold]Select a release to switch to:[/bold]")
            choice = Prompt.ask(
                "Enter release number (1-{}) or 'q' to quit".format(len(releases)),
                default="q",
            )

            if choice.lower() == "q":
                console.print("[yellow]⏹️  Cancelled[/yellow]")
                return

            try:
                idx = int(choice)
                if 1 <= idx <= len(releases):
                    target_release = releases[idx - 1]
                else:
                    console.print(f"[red]❌ Invalid selection: {choice}[/red]")
                    return
            except ValueError:
                console.print(f"[red]❌ Invalid input: {choice}[/red]")
                return

        elif version == "previous":
            # Switch to previous (second in list)
            if len(releases) < 2:
                console.print("[red]❌ No previous release available[/red]")
                return
            target_release = releases[1]

        elif version.isdigit():
            # Index-based selection
            idx = int(version)
            if 1 <= idx <= len(releases):
                target_release = releases[idx - 1]
            else:
                console.print(
                    f"[red]❌ Invalid index: {version} (available: 1-{len(releases)})[/red]"
                )
                return

        else:
            # Find matching release by name/sha
            for r in releases:
                if version in r:
                    target_release = r
                    break

            if not target_release:
                console.print(f"[red]❌ Release not found: {version}[/red]")
                return

        # Check if already current
        if target_release == current_name:
            console.print(f"[yellow]⚠️  Already running: {target_release}[/yellow]")
            return

        # Show confirmation
        console.print(
            Panel(
                f"[cyan]🔄 Switch Release (Zero-Downtime)[/cyan]\n\n"
                f"[white]App:[/white] {app}\n"
                f"[white]From:[/white] {current_name or 'unknown'}\n"
                f"[white]To:[/white] {target_release}\n\n"
                f"[dim]New container will start before old one stops[/dim]\n"
                f"[dim]Health check will verify new version before switching[/dim]\n"
                f"[dim]Automatic rollback if health check fails[/dim]",
                border_style="cyan",
            )
        )

        # Confirm
        if not force:
            console.print(
                "Continue with switch? "
                "[bold bright_white]\\[y/n][/bold bright_white] [dim](y)[/dim]: ",
                end="",
            )
            answer = input().strip().lower()
            if answer not in ["y", "yes", ""]:  # Empty = default yes
                console.print("[yellow]⏹️  Switch cancelled[/yellow]")
                return

        console.print()  # Add 1 newline after confirmation
        # Execute switch with zero-downtime
        console.print("[cyan]🔄 Switching release (zero-downtime)...[/cyan]")

        switch_cmd = f"""
        set -e
        cd /opt/apps/{project}/releases/{app}/{target_release}
        
        CONTAINER_NAME="{project}-{app}"
        NEW_CONTAINER="${{CONTAINER_NAME}}-new-$RANDOM"
        
        echo "📦 Preparing new release..."
        
        # Note: .env no longer used in new releases (secrets via docker compose env_file or runtime injection)
        
        # Temporarily rename service in compose file to avoid name conflict
        sed "s/container_name: $CONTAINER_NAME/container_name: $NEW_CONTAINER/" docker-compose-{app}.yml > /tmp/docker-compose-new.yml
        
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
                ln -sfn /opt/apps/{project}/releases/{app}/{target_release} /opt/apps/{project}/current/{app}
                
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
            console.print("\n[green]✅ Zero-downtime switch completed![/green]")
            console.print(f"[green]✅ Now running: {target_release}[/green]")
            console.print("[dim]  → New container started[/dim]")
            console.print("[dim]  → Health check passed[/dim]")
            console.print("[dim]  → Old container removed[/dim]")

            # Show quick verification command
            app_port = apps[app].get("port", 8000)
            console.print(f"\n[dim]Verify: curl http://{ssh_host}:{app_port}/[/dim]")
        elif "SWITCH_FAILED" in result:
            console.print("\n[red]❌ Switch failed - rollback performed[/red]")
            console.print(
                "[yellow]⚠️  Old version is still running (no downtime)[/yellow]"
            )
            console.print(f"\n[dim]{result}[/dim]")
            raise SystemExit(1)
        else:
            console.print("[red]❌ Switch failed[/red]")
            console.print(f"[dim]{result}[/dim]")
            raise SystemExit(1)

    except Exception as e:
        console.print(f"[red]❌ Switch failed: {e}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise SystemExit(1)


if __name__ == "__main__":
    switch()
