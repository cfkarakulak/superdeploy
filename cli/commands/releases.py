"""SuperDeploy CLI - Releases and Rollback commands"""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-n", "--limit", default=10, help="Number of releases to show")
def releases(project, app, limit):
    """
    Show release history for an app (last 5 releases kept)

    \b
    Examples:
      superdeploy releases -p cheapa -a api          # Show all releases
      superdeploy releases -p cheapa -a api -n 3     # Show last 3

    \b
    Shows:
    - Release timestamp
    - Git SHA
    - Current/Previous status
    - Quick rollback command
    """
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
        
        # Get VM IP from .env
        from cli.utils import load_env
        env = load_env(project=project)
        
        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            console.print(f"[red]❌ VM IP not found in .env: {ip_key}[/red]")
            return
        
        ssh_host = env[ip_key]
        ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
        ssh_user = "superdeploy"
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return

    console.print(f"[cyan]📋 Fetching release history for [bold]{app}[/bold]...[/cyan]")

    # List releases from filesystem
    list_cmd = f"ls -t /opt/apps/{project}/releases/{app}/ 2>/dev/null || echo 'NO_RELEASES'"

    try:
        releases_output = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
        )
        
        if releases_output.strip() == "NO_RELEASES":
            console.print(f"[yellow]⚠️  No releases found for {app}[/yellow]")
            console.print("[dim]Deploy the app first: git push origin production[/dim]")
            return
        
        releases = [r.strip() for r in releases_output.strip().split('\n') if r.strip()]
        
        if not releases:
            console.print(f"[yellow]⚠️  No releases found[/yellow]")
            return
        
        # Get current release
        current_cmd = f"readlink /opt/apps/{project}/current/{app} 2>/dev/null || echo 'NONE'"
        current_release = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
        ).strip()
        
        current_name = current_release.split('/')[-1] if current_release != 'NONE' else None
        
        # Build table
        table = Table(title=f"Release History - {app.upper()}", show_header=True)
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Timestamp", style="green")
        table.add_column("Git SHA", style="yellow")
        table.add_column("Status", style="bold")
        
        for idx, release in enumerate(releases[:limit], 1):
            parts = release.split('_')
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
        
        console.print("\n")
        console.print(table)
        
        # Show rollback hints
        console.print(f"\n[bold]Quick Commands:[/bold]")
        console.print(f"  Rollback to previous: [cyan]superdeploy rollback -p {project} -a {app}[/cyan]")
        if len(releases) > 1:
            console.print(f"  Rollback to specific: [cyan]superdeploy rollback -p {project} -a {app} -v {releases[1]}[/cyan]")
        console.print(f"\n[dim]💡 System keeps last 5 releases for instant rollback[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Failed to fetch releases: {e}[/red]")
        raise SystemExit(1)


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name")
@click.option("--version", "-v", help="Release version (timestamp_sha or 'previous')")
@click.option("--force", is_flag=True, help="Skip confirmation")
def rollback(project, app, version, force):
    """
    Instant rollback to a previous release (1-2 seconds)

    \b
    Examples:
      superdeploy rollback -p cheapa -a api              # Rollback to previous
      superdeploy rollback -p cheapa -a api -v 20251030_abc1234  # Specific release

    \b
    How it works:
    - Changes symlink to previous release
    - Restarts container with old image
    - Zero downtime (1-2 seconds)
    """
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
        
        # Get VM IP from .env
        from cli.utils import load_env
        env = load_env(project=project)
        
        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            console.print(f"[red]❌ VM IP not found in .env: {ip_key}[/red]")
            return
        
        ssh_host = env[ip_key]
        ssh_key = os.path.expanduser("~/.ssh/superdeploy_deploy")
        ssh_user = "superdeploy"
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return
    
    # List available releases
    console.print(f"[cyan]📋 Fetching releases for {app}...[/cyan]")
    
    list_cmd = f"ls -t /opt/apps/{project}/releases/{app}/ 2>/dev/null || echo 'NO_RELEASES'"
    
    try:
        releases_output = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
        )
        
        if releases_output.strip() == "NO_RELEASES":
            console.print(f"[red]❌ No releases found for {app}[/red]")
            console.print("[dim]Deploy the app first: git push origin production[/dim]")
            return
        
        releases = [r.strip() for r in releases_output.strip().split('\n') if r.strip()]
        
        if not releases:
            console.print(f"[red]❌ No releases found[/red]")
            return
        
        # Show releases
        table = Table(title=f"Available Releases - {app.upper()}")
        table.add_column("#", style="cyan")
        table.add_column("Release", style="green")
        table.add_column("SHA", style="yellow")
        table.add_column("Status", style="bold")
        
        # Get current release from running container image tag (most reliable)
        current_cmd = f"""
        CONTAINER_NAME="{project}-{app}"
        if docker ps --filter "name=$CONTAINER_NAME" --format "{{{{.Names}}}}" | grep -q "^$CONTAINER_NAME$"; then
            # Get SHA from image tag (e.g., c100394/api:a89f68f...)
            IMAGE=$(docker inspect $CONTAINER_NAME --format '{{{{.Config.Image}}}}' 2>/dev/null || echo '')
            if [ -n "$IMAGE" ]; then
                # Extract SHA from image tag (after colon)
                CURRENT_SHA=$(echo "$IMAGE" | cut -d':' -f2)
                if [ -n "$CURRENT_SHA" ]; then
                    # Find release directory matching this SHA (first 7 chars)
                    cd /opt/apps/{project}/releases/{app}/ 2>/dev/null || exit 0
                    for dir in */; do
                        if [[ "$dir" == *"${{CURRENT_SHA:0:7}}"* ]]; then
                            echo "${{dir%/}}"
                            exit 0
                        fi
                    done
                fi
            fi
        fi
        # Fallback to symlink
        readlink /opt/apps/{project}/current/{app} 2>/dev/null | xargs basename || echo 'NONE'
        """
        current_release = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
        ).strip()
        
        current_name = current_release if current_release != 'NONE' else None
        
        for idx, release in enumerate(releases[:10], 1):
            parts = release.split('_')
            sha = parts[-1] if len(parts) > 1 else "unknown"
            status = "✅ CURRENT" if release == current_name else ""
            table.add_row(str(idx), release, sha, status)
        
        console.print("\n")
        console.print(table)
        
        # Determine target release
        if not version or version == "previous":
            # Rollback to previous (second in list)
            if len(releases) < 2:
                console.print("[red]❌ No previous release available[/red]")
                return
            target_release = releases[1]
        else:
            # Find matching release
            target_release = None
            for r in releases:
                if version in r:
                    target_release = r
                    break
            
            if not target_release:
                console.print(f"[red]❌ Release not found: {version}[/red]")
                return
        
        console.print(
            Panel(
                f"[yellow]⚠️  Rollback[/yellow]\n\n"
                f"[white]App:[/white] {app}\n"
                f"[white]From:[/white] {current_name or 'unknown'}\n"
                f"[white]To:[/white] {target_release}\n\n"
                f"[dim]This will switch to the previous release (1-2 seconds)[/dim]",
                border_style="yellow",
            )
        )
        
        # Confirm
        if not force:
            if not Confirm.ask("Continue with rollback?"):
                console.print("[yellow]⏹️  Rollback cancelled[/yellow]")
                return
        
        # Execute instant rollback
        console.print("[cyan]🔄 Executing instant rollback...[/cyan]")
        
        rollback_cmd = f"""
        set -e
        cd /opt/apps/{project}/releases/{app}/{target_release}
        
        # Update symlink (atomic operation)
        ln -sfn /opt/apps/{project}/releases/{app}/{target_release} /opt/apps/{project}/current/{app}
        
        # Copy .env to /tmp/decrypted.env for docker-compose
        cp .env /tmp/decrypted.env
        
        # Stop and remove existing container (graceful)
        if docker ps -q --filter "name={project}-{app}" | grep -q .; then
            docker stop {project}-{app} 2>/dev/null || true
            docker rm {project}-{app} 2>/dev/null || true
        fi
        
        # Start container with old image (labels are in compose file)
        docker compose -f docker-compose-{app}.yml up -d --wait
        
        # Cleanup
        rm -f /tmp/decrypted.env
        
        echo "ROLLBACK_SUCCESS"
        """
        
        result = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=rollback_cmd
        )
        
        if "ROLLBACK_SUCCESS" in result:
            console.print("[green]✅ Rollback completed in 1-2 seconds![/green]")
            console.print(f"[green]✅ Now running: {target_release}[/green]")
            
            # Send email notification
            try:
                send_rollback_notification(
                    project=project,
                    app=app,
                    from_version=current_name or "unknown",
                    to_version=target_release,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_key=ssh_key,
                    env=env
                )
            except Exception as e:
                console.print(f"[yellow]⚠️  Email notification failed: {e}[/yellow]")
        else:
            console.print(f"[red]❌ Rollback failed[/red]")
            console.print(f"[dim]{result}[/dim]")
            
    except Exception as e:
        console.print(f"[red]❌ Rollback failed: {e}[/red]")
        raise SystemExit(1)


def send_rollback_notification(project, app, from_version, to_version, ssh_host, ssh_user, ssh_key, env):
    """Send email notification for rollback"""
    import datetime
    
    alert_email = env.get("ALERT_EMAIL")
    if not alert_email:
        return
    
    console.print(f"[cyan]📧 Sending rollback notification to {alert_email}...[/cyan]")
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    
    # Get service port
    service_port = ""
    if app == "api":
        service_port = "8000"
    elif app == "dashboard":
        service_port = "3000"
    elif app == "services":
        service_port = "8001"
    
    email_cmd = f"""
    ALERT_EMAIL="{alert_email}"
    PROJECT="{project}"
    SERVICE="{app}"
    FROM_VERSION="{from_version}"
    TO_VERSION="{to_version}"
    TIMESTAMP="{timestamp}"
    VM_IP="{ssh_host}"
    SERVICE_PORT="{service_port}"
    
    # Install mailutils if needed
    if ! command -v mail &> /dev/null; then
        export DEBIAN_FRONTEND=noninteractive
        sudo apt-get update -qq && sudo apt-get install -y mailutils postfix 2>&1 | grep -v "^Get:" || exit 0
    fi
    
    # Send HTML email
    {{
        echo "Content-Type: text/html; charset=UTF-8"
        echo "Subject: ⏮️  Rollback: $PROJECT/$SERVICE"
        echo ""
        echo "<html><body style='font-family: Arial, sans-serif; color: #333;'>"
        echo "<h2 style='color: #ff9800;'>⏮️  Rollback Executed</h2>"
        echo "<table style='border-collapse: collapse; width: 100%; max-width: 600px;'>"
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>Project</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'>$PROJECT</td></tr>"
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>Service</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'>$SERVICE</td></tr>"
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>From</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'><code>$FROM_VERSION</code></td></tr>"
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>To</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'><code style='color: #28a745;'>$TO_VERSION</code></td></tr>"
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>VM</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'>$VM_IP</td></tr>"
        if [ -n "$SERVICE_PORT" ]; then
            echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>URL</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'><a href='http://$VM_IP:$SERVICE_PORT'>http://$VM_IP:$SERVICE_PORT</a></td></tr>"
        fi
        echo "<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>Time</strong></td><td style='padding: 8px; border-bottom: 1px solid #ddd;'>$TIMESTAMP</td></tr>"
        echo "</table>"
        echo "<p style='margin-top: 20px; font-size: 12px; color: #666;'>SuperDeploy automated notification</p>"
        echo "</body></html>"
    }} | mail -a "Content-Type: text/html" -s "⏮️  Rollback: $PROJECT/$SERVICE" "$ALERT_EMAIL" 2>&1
    """
    
    try:
        ssh_command(host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=email_cmd)
        console.print("[green]✅ Email notification sent[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Email failed: {e}[/yellow]")
