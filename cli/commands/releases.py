"""SuperDeploy CLI - Releases command"""

import click
from rich.console import Console
from cli.ui_components import show_header
from rich.table import Table
from cli.utils import load_env, ssh_command

console = Console()


@click.command(name="releases:list")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-n", "--limit", default=10, help="Number of releases to show")
def releases_list(project, app, limit):
    """
    Show release history for an app (last 5 releases kept)

    \b
    Examples:
      superdeploy releases:list -p cheapa -a api          # Show all releases
      superdeploy releases:list -p cheapa -a api -n 3     # Show last 3

    \b
    Shows:
    - Release timestamp
    - Git SHA
    - Current/Previous status
    - Use 'superdeploy releases:rollback' to change versions
    """
    show_header(
        title="Release History",
        project=project,
        app=app,
        details={"Limit": str(limit)},
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

        # Get VM IP from .env
        env = load_env(project=project)

        ip_key = f"{vm_role.upper()}_0_EXTERNAL_IP"
        if ip_key not in env:
            console.print(f"[red]❌ VM IP not found in .env: {ip_key}[/red]")
            return

        ssh_host = env[ip_key]
        ssh_key = os.path.expanduser(ssh_key_path)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return

    console.print(f"[cyan]📋 Fetching release history for [bold]{app}[/bold]...[/cyan]")

    # List releases from filesystem
    list_cmd = (
        f"ls -t /opt/apps/{project}/releases/{app}/ 2>/dev/null || echo 'NO_RELEASES'"
    )

    try:
        releases_output = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=list_cmd
        )

        if releases_output.strip() == "NO_RELEASES":
            console.print(f"[yellow]⚠️  No releases found for {app}[/yellow]")
            console.print("[dim]Deploy the app first: git push origin production[/dim]")
            return

        releases_list = [
            r.strip() for r in releases_output.strip().split("\n") if r.strip()
        ]

        if not releases_list:
            console.print("[yellow]⚠️  No releases found[/yellow]")
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
            title=f"Release History - {app.upper()}",
            show_header=True,
            title_justify="left",
            padding=(0, 1),
        )
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Timestamp", style="green")
        table.add_column("Git SHA", style="yellow")
        table.add_column("Status", style="bold")

        for idx, release in enumerate(releases_list[:limit], 1):
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

        console.print("\n")
        console.print(table)

        # Show switch hints
        console.print("\n[bold]Quick Commands:[/bold]")
        console.print(
            f"  Switch to any version: [cyan]superdeploy switch -p {project} -a {app}[/cyan]"
        )
        if len(releases_list) > 1:
            console.print(
                f"  Switch to specific: [cyan]superdeploy switch -p {project} -a {app} -v 2[/cyan]"
            )
        console.print(
            "\n[dim]💡 System keeps last 5 releases for instant switching[/dim]"
        )

    except Exception as e:
        console.print(f"[red]❌ Failed to fetch releases: {e}[/red]")
        raise SystemExit(1)
