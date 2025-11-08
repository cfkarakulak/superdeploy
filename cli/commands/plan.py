"""SuperDeploy CLI - Plan command (like terraform plan)"""

import click
from rich.console import Console
from cli.ui_components import show_header

console = Console()


@click.command()
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--detailed", is_flag=True, help="Show detailed diff")
def plan(project, json_output, detailed):
    """
    Show what changes will be applied (like terraform plan)

    Analyzes project.yml and compares with last applied state.
    Shows what will be created, modified, or deleted.

    Example:
        superdeploy myproject:plan
        superdeploy myproject:plan --detailed
    """

    if not json_output:
        show_header(
            title="Deployment Plan",
            subtitle="Analyzing configuration changes",
            project=project,
            console=console,
        )

    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    from cli.state_manager import StateManager

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    # Load config
    config_loader = ConfigLoader(projects_dir)

    try:
        project_config = config_loader.load_project(project)
    except FileNotFoundError:
        console.print(f"[red]❌ Project not found: {project}[/red]")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        raise SystemExit(1)

    # Detect changes
    state_mgr = StateManager(project_root, project)
    changes, state = state_mgr.detect_changes(project_config)

    # JSON output
    if json_output:
        import json

        print(json.dumps(changes, indent=2))
        return

    # No changes
    if not changes["has_changes"]:
        console.print("\n[green]✅ No changes detected.[/green]\n")
        console.print("Infrastructure is up to date with project.yml\n")
        return

    # Display changes
    console.print()

    # VMs
    if (
        changes["vms"]["added"]
        or changes["vms"]["removed"]
        or changes["vms"]["modified"]
    ):
        console.print("━" * 60)
        console.print("[bold cyan]🖥️  VIRTUAL MACHINES[/bold cyan]")
        console.print("━" * 60)
        console.print()

        config = project_config.raw_config

        # Added
        for vm_name in changes["vms"]["added"]:
            vm_config = config["vms"][vm_name]
            console.print(f"  [green]+ {vm_name}[/green] (new VM)")
            console.print(f"    Machine: {vm_config.get('machine_type', 'e2-small')}")
            console.print(f"    Disk: {vm_config.get('disk_size', 20)}GB")
            services = vm_config.get("services", [])
            if services:
                console.print(f"    Services: {', '.join(services)}")
            console.print()

        # Modified
        for vm_change in changes["vms"]["modified"]:
            vm_name = vm_change["name"]
            old = vm_change["old"]
            new = vm_change["new"]

            console.print(f"  [yellow]~ {vm_name}[/yellow] (modified)")

            if old.get("machine_type") != new.get("machine_type"):
                console.print(
                    f"    Machine: {old.get('machine_type')} → [yellow]{new.get('machine_type')}[/yellow]"
                )
            else:
                console.print(f"    Machine: {new.get('machine_type')} (unchanged)")

            if old.get("disk_size") != new.get("disk_size"):
                console.print(
                    f"    Disk: {old.get('disk_size')}GB → [yellow]{new.get('disk_size')}GB[/yellow]"
                )

            old_services = set(old.get("services", []))
            new_services = set(new.get("services", []))

            if old_services != new_services:
                added_services = new_services - old_services
                removed_services = old_services - new_services

                if added_services:
                    console.print(
                        f"    Services +: [green]{', '.join(added_services)}[/green]"
                    )
                if removed_services:
                    console.print(
                        f"    Services -: [red]{', '.join(removed_services)}[/red]"
                    )

            console.print()

        # Removed
        for vm_name in changes["vms"]["removed"]:
            console.print(f"  [red]- {vm_name}[/red] (will be destroyed)")
            console.print()

    # Addons
    if changes["addons"]["added"] or changes["addons"]["removed"]:
        console.print("━" * 60)
        console.print("[bold cyan]🔌 ADDONS[/bold cyan]")
        console.print("━" * 60)
        console.print()

        # Show unchanged addons if state exists
        if state and state.get("addons"):
            for addon_name in state["addons"]:
                if (
                    addon_name not in changes["addons"]["added"]
                    and addon_name not in changes["addons"]["removed"]
                ):
                    console.print(f"  [dim]✅ {addon_name} (unchanged)[/dim]")

        # Added
        for addon_name in changes["addons"]["added"]:
            console.print(f"  [green]+ {addon_name}[/green] (will be installed)")

        # Removed
        for addon_name in changes["addons"]["removed"]:
            console.print(f"  [red]- {addon_name}[/red] (will be removed)")

        console.print()

    # Apps
    if (
        changes["apps"]["added"]
        or changes["apps"]["removed"]
        or changes["apps"]["modified"]
    ):
        console.print("━" * 60)
        console.print("[bold cyan]📦 APPLICATIONS[/bold cyan]")
        console.print("━" * 60)
        console.print()

        config = project_config.raw_config

        # Show unchanged apps if state exists
        if state and state.get("apps"):
            for app_name in state["apps"]:
                if (
                    app_name not in changes["apps"]["added"]
                    and app_name not in changes["apps"]["removed"]
                    and not any(
                        a["name"] == app_name for a in changes["apps"]["modified"]
                    )
                ):
                    console.print(f"  [dim]✅ {app_name} (no changes)[/dim]")

        # Added
        for app_name in changes["apps"]["added"]:
            app_config = config["apps"][app_name]
            console.print(f"  [green]+ {app_name}[/green] (new app)")
            console.print(f"    Path: {app_config.get('path')}")
            console.print(f"    VM: {app_config.get('vm')}")
            console.print("    Workflows: will be generated")
            console.print()

        # Modified
        for app_change in changes["apps"]["modified"]:
            app_name = app_change["name"]
            old = app_change["old"]
            new = app_change["new"]

            console.print(f"  [yellow]~ {app_name}[/yellow] (modified)")

            if old.get("path") != new.get("path"):
                console.print(
                    f"    Path: {old.get('path')} → [yellow]{new.get('path')}[/yellow]"
                )

            if old.get("vm") != new.get("vm"):
                console.print(
                    f"    VM: {old.get('vm')} → [yellow]{new.get('vm')}[/yellow]"
                )

            console.print("    Workflows: will be regenerated")
            console.print()

        # Removed
        for app_name in changes["apps"]["removed"]:
            console.print(f"  [red]- {app_name}[/red] (removed from config)")
            console.print()

    # Impact analysis
    console.print("━" * 60)
    console.print("[bold cyan]📈 IMPACT ANALYSIS[/bold cyan]")
    console.print("━" * 60)
    console.print()

    impact_items = []

    if changes["needs_generate"]:
        impact_items.append("• Generate workflows for apps")

    if changes["needs_terraform"]:
        impact_items.append("• Provision/modify infrastructure (Terraform)")
        if changes["vms"]["modified"]:
            impact_items.append(
                "  [yellow]⚠ VM changes may cause brief downtime[/yellow]"
            )

    if changes["needs_ansible"]:
        impact_items.append("• Configure services (Ansible)")

    if changes["needs_sync"]:
        impact_items.append("• Sync secrets to GitHub")

    if not impact_items:
        impact_items.append("• No infrastructure changes needed")

    for item in impact_items:
        console.print(f"  {item}")

    console.print()

    # Downtime estimation
    if changes["vms"]["modified"]:
        console.print("  [bold]Estimated downtime:[/bold] 2-3 minutes (VM restart)")
    elif changes["vms"]["added"]:
        console.print("  [bold]Estimated time:[/bold] 3-5 minutes (VM creation)")
    else:
        console.print("  [bold]Downtime:[/bold] None")

    console.print()

    # Next steps
    console.print("━" * 60)
    console.print()
    console.print("[bold]To apply these changes:[/bold]")
    console.print(f"  superdeploy {project}:up")
    console.print()
