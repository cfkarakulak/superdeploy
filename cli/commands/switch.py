"""SuperDeploy CLI - Switch between releases"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from cli.utils import load_env, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--version", "-v", help="Release version (timestamp_sha, index number, or 'previous')")
@click.option("--force", is_flag=True, help="Skip confirmation")
def switch(project, app, version, force):
    """
    Switch between any release version (forward or backward)

    \b
    Examples:
      superdeploy switch -p cheapa -a api                           # Interactive: show list and select
      superdeploy switch -p cheapa -a api -v 2                      # Switch to release #2
      superdeploy switch -p cheapa -a api -v 20251030_143312_3a4a89d  # Switch to specific release
      superdeploy switch -p cheapa -a api -v previous               # Switch to previous release

    \b
    Features:
    - Navigate forward/backward between any releases
    - Interactive selection if no version specified
    - Zero-downtime switching (1-2 seconds)
    - Keeps last 5 releases for instant switching
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
    console.print(f"[cyan]📋 Fetching releases for {app}...[/cyan]\n")
    
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
        
        # Get current release
        current_cmd = f"readlink /opt/apps/{project}/current/{app} 2>/dev/null || echo 'NONE'"
        current_release = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=current_cmd
        ).strip()
        
        current_name = current_release.split('/')[-1] if current_release != 'NONE' else None
        
        # Build table
        table = Table(title=f"Available Releases - {app.upper()}", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Release", style="green")
        table.add_column("SHA", style="yellow", width=10)
        table.add_column("Status", style="bold", width=12)
        
        for idx, release in enumerate(releases[:10], 1):
            parts = release.split('_')
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
                default="q"
            )
            
            if choice.lower() == 'q':
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
                console.print(f"[red]❌ Invalid index: {version} (available: 1-{len(releases)})[/red]")
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
                f"[cyan]🔄 Switch Release[/cyan]\n\n"
                f"[white]App:[/white] {app}\n"
                f"[white]From:[/white] {current_name or 'unknown'}\n"
                f"[white]To:[/white] {target_release}\n\n"
                f"[dim]This will switch to the selected release (1-2 seconds)[/dim]",
                border_style="cyan",
            )
        )
        
        # Confirm
        if not force:
            if not Confirm.ask("Continue with switch?"):
                console.print("[yellow]⏹️  Switch cancelled[/yellow]")
                return
        
        # Execute switch
        console.print("[cyan]🔄 Switching release...[/cyan]")
        
        switch_cmd = f"""
        set -e
        cd /opt/apps/{project}/releases/{app}/{target_release}
        
        # Update symlink (atomic operation)
        ln -sfn /opt/apps/{project}/releases/{app}/{target_release} /opt/apps/{project}/current/{app}
        
        # Copy .env to /tmp/decrypted.env for docker-compose
        cp .env /tmp/decrypted.env
        
        # Stop and remove existing container
        docker stop {project}-{app} 2>/dev/null || true
        docker rm {project}-{app} 2>/dev/null || true
        
        # Start container with selected image
        docker compose -f docker-compose-{app}.yml up -d --wait
        
        # Cleanup
        rm -f /tmp/decrypted.env
        
        echo "SWITCH_SUCCESS"
        """
        
        result = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=switch_cmd
        )
        
        if "SWITCH_SUCCESS" in result:
            console.print("[green]✅ Switch completed in 1-2 seconds![/green]")
            console.print(f"[green]✅ Now running: {target_release}[/green]")
            
            # Show quick verification command
            app_port = apps[app].get("port", 8000)
            console.print(f"\n[dim]Verify: curl http://{ssh_host}:{app_port}/[/dim]")
        else:
            console.print(f"[red]❌ Switch failed[/red]")
            console.print(f"[dim]{result}[/dim]")
            
    except Exception as e:
        console.print(f"[red]❌ Switch failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise SystemExit(1)


if __name__ == "__main__":
    switch()
