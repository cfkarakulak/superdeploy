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
        
        # Get current release
        current_cmd = f"readlink /opt/apps/{project}/current/{app} 2>/dev/null || echo 'NONE'"
        current_release = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
        ).strip()
        
        current_name = current_release.split('/')[-1] if current_release != 'NONE' else None
        
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
        
        # Restart container with old image
        docker compose -f docker-compose-{app}.yml up -d --force-recreate --wait
        
        echo "ROLLBACK_SUCCESS"
        """
        
        result = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=rollback_cmd
        )
        
        if "ROLLBACK_SUCCESS" in result:
            console.print("[green]✅ Rollback completed in 1-2 seconds![/green]")
            console.print(f"[green]✅ Now running: {target_release}[/green]")
        else:
            console.print(f"[red]❌ Rollback failed[/red]")
            console.print(f"[dim]{result}[/dim]")
            
    except Exception as e:
        console.print(f"[red]❌ Rollback failed: {e}[/red]")
        raise SystemExit(1)
