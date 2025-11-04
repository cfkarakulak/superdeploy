"""SuperDeploy CLI - Validate command"""

import click
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header
from cli.utils import (
    get_project_path,
    validate_project as validate_project_exists,
    get_project_root,
)

console = Console()


def get_recommended_addons():
    """
    Discover recommended addons dynamically based on category.

    Returns:
        list: List of recommended addon names
    """
    from cli.core.addon_loader import AddonLoader

    try:
        project_root = get_project_root()
        addons_dir = project_root / "addons"
        addon_loader = AddonLoader(addons_dir)

        # Get all available addons
        available = addon_loader.list_available_addons()

        # Filter to common categories (database, cache, queue)
        recommended = [
            addon_name
            for addon_name, metadata in available.items()
            if metadata.get("category") in ["database", "cache", "queue"]
        ]

        return recommended
    except Exception as e:
        # Fallback to empty list if addon loading fails
        console.print(f"[dim]Could not load recommended addons: {e}[/dim]")
        return []


@click.command(name="validate:project")
@click.option("--project", "-p", required=True, help="Project name")
def validate_project(project):
    """
    Validate project configuration

    \b
    Examples:
      superdeploy validate -p acme

    \b
    This command validates:
    - config.yml structure and required fields
    - Port assignments (no conflicts)
    - Service definitions
    - Repository URLs
    - Network configuration
    """
    show_header(
        title="Validate Project Configuration",
        project=project,
        console=console,
    )

    # Validate project exists
    try:
        validate_project_exists(project)
        project_path = get_project_path(project)
    except Exception as e:
        console.print(f"[red]❌ Project validation failed: {e}[/red]")
        raise SystemExit(1)

    # Load config using ConfigLoader
    from cli.core.config_loader import ConfigLoader

    project_root = get_project_root()

    try:
        config_loader = ConfigLoader(project_root / "projects")
        project_config_obj = config_loader.load_project(project)
        config = project_config_obj.raw_config
    except FileNotFoundError:
        console.print(f"[red]❌ Project config not found for: {project}[/red]")
        console.print(f"[dim]Run: superdeploy init -p {project}[/dim]")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]❌ Invalid config: {e}[/red]")
        raise SystemExit(1)

    errors = []
    warnings = []

    # Validation checks
    console.print("\n[bold]Running validation checks...[/bold]\n")

    # 1. Required fields
    required_fields = ["project", "services", "ports", "addons", "github"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
        else:
            console.print(f"[green]✓[/green] Required field: {field}")

    # 2. Services validation
    if "services" in config:
        services = config["services"]
        if not services or len(services) == 0:
            errors.append("No services defined")
        else:
            console.print(f"[green]✓[/green] Services defined: {len(services)}")

            # Check each service has port mapping
            for service in services:
                if "ports" not in config or service not in config["ports"]:
                    warnings.append(f"Service '{service}' has no port mapping")

    # 3. Port conflicts
    if "ports" in config:
        external_ports = []
        for service, port_config in config["ports"].items():
            if "external" in port_config:
                ext_port = port_config["external"]
                if ext_port in external_ports:
                    errors.append(
                        f"Port conflict: {ext_port} used by multiple services"
                    )
                external_ports.append(ext_port)

        console.print(f"[green]✓[/green] Port assignments: {len(external_ports)} ports")

    # 4. Addons
    if "addons" in config:
        recommended_addons = get_recommended_addons()
        for addon in recommended_addons:
            if addon not in config["addons"]:
                warnings.append(f"Addon '{addon}' not configured")
            else:
                console.print(f"[green]✓[/green] Core service: {addon}")

    # 5. GitHub repositories
    if "github" in config and "repositories" in config["github"]:
        repos = config["github"]["repositories"]
        console.print(f"[green]✓[/green] GitHub repositories: {len(repos)}")

        # Check each service has a repo
        if "services" in config:
            for service in config["services"]:
                if service not in repos:
                    warnings.append(f"Service '{service}' has no GitHub repository")

    # 6. Network configuration
    if "network" in config and "subnet" in config["network"]:
        console.print(f"[green]✓[/green] Network subnet: {config['network']['subnet']}")
    else:
        warnings.append("Network subnet not configured")

    # Display results
    console.print("\n[bold]Validation Results:[/bold]\n")

    if errors:
        console.print("[bold red]❌ Errors:[/bold red]")
        for error in errors:
            console.print(f"  • {error}")
        console.print()

    if warnings:
        console.print("[bold yellow]⚠️  Warnings:[/bold yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")
        console.print()

    if not errors and not warnings:
        console.print("[bold green]✅ Configuration is valid![/bold green]")

        # Display summary table
        table = Table(
            title="Configuration Summary", title_justify="left", padding=(0, 1)
        )
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Project", config.get("project", "N/A"))
        table.add_row("Services", str(len(config.get("services", []))))
        table.add_row("Ports", str(len(config.get("ports", {}))))
        table.add_row("Addons", str(len(config.get("addons", {}))))
        table.add_row(
            "Repositories", str(len(config.get("github", {}).get("repositories", {})))
        )

        console.print()
        console.print(table)

        raise SystemExit(0)
    elif errors:
        console.print("[bold red]❌ Validation failed with errors[/bold red]")
        raise SystemExit(1)
    else:
        console.print("[bold yellow]⚠️  Validation passed with warnings[/bold yellow]")
        raise SystemExit(0)


@click.command(name="validate:addons")
@click.option("--project", "-p", help="Validate addons for specific project")
@click.option("--addon", "-a", help="Validate specific addon")
@click.option(
    "--fix", is_flag=True, help="Attempt to auto-fix issues (not implemented yet)"
)
def validate_addons(project, addon, fix):
    """
    Validate addon structure and configuration

    \b
    Examples:
      superdeploy validate addons                    # Validate all addons
      superdeploy validate addons -a postgres        # Validate specific addon
      superdeploy validate addons -p acme            # Validate addons for project
      superdeploy validate addons --fix              # Auto-fix issues (future)

    \b
    This command validates:
    - Required files (addon.yml, docker-compose.yml.j2)
    - Metadata fields (name, description, version, category)
    - Compose template structure
    - Healthcheck configuration
    - Ansible tasks (anti-patterns)
    """
    from cli.core.addon_validator import AddonValidator

    show_header(
        title="Validate Addons",
        details={"Target": addon if addon else "All addons"},
        console=console,
    )

    if fix:
        console.print("[yellow]⚠️  Auto-fix is not yet implemented[/yellow]\n")

    # Get addons path
    project_root = get_project_root()
    addons_path = project_root / "addons"

    # Initialize validator
    validator = AddonValidator(addons_path)

    # Validate addon(s)
    if addon:
        results = [validator.validate_addon(addon)]
    elif project:
        # Load project config to get enabled addons
        from cli.core.config_loader import ConfigLoader

        try:
            config_loader = ConfigLoader(project_root / "projects")
            project_config = config_loader.load_project(project)
            enabled_addons = project_config.to_ansible_vars().get("enabled_addons", [])

            if not enabled_addons:
                console.print(
                    f"[yellow]⚠️  No addons enabled for project '{project}'[/yellow]"
                )
                raise SystemExit(0)

            console.print(
                f"[dim]Validating {len(enabled_addons)} addons for project '{project}'...[/dim]\n"
            )
            results = [validator.validate_addon(a) for a in enabled_addons]
        except Exception as e:
            console.print(f"[red]❌ Error loading project: {e}[/red]")
            raise SystemExit(1)
    else:
        results = validator.validate_all_addons()

    if not results:
        console.print("[yellow]⚠️  No addons found to validate[/yellow]")
        raise SystemExit(0)

    # Display results
    total_passed = 0
    total_failed = 0

    for result in results:
        # Create status indicator
        if result.passed:
            status = "[green]✓ PASS[/green]"
            total_passed += 1
        else:
            status = "[red]✗ FAIL[/red]"
            total_failed += 1

        # Display addon header
        console.print(f"\n{status} [bold]{result.addon_name}[/bold]")

        if result.error_count > 0:
            console.print(f"  [red]Errors: {result.error_count}[/red]")
        if result.warning_count > 0:
            console.print(f"  [yellow]Warnings: {result.warning_count}[/yellow]")

        # Display checks
        for check in result.checks:
            if check.severity == "info" and check.passed:
                continue  # Skip passed info checks for brevity

            # Color based on severity and status
            if check.passed:
                icon = "✓"
                color = "green"
            else:
                icon = "✗"
                if check.severity == "error":
                    color = "red"
                elif check.severity == "warning":
                    color = "yellow"
                else:
                    color = "dim"

            console.print(f"    [{color}]{icon}[/{color}] {check.message}")

            # Show fix suggestion if available
            if not check.passed and check.fix_suggestion:
                console.print(f"      [dim]→ {check.fix_suggestion}[/dim]")

    # Summary
    console.print("\n" + "─" * 50)
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total addons: {len(results)}")
    console.print(f"  [green]Passed: {total_passed}[/green]")
    console.print(f"  [red]Failed: {total_failed}[/red]")

    # Create summary table
    if total_failed > 0:
        console.print("\n[bold red]Failed Addons:[/bold red]")

        table = Table(
            title="Addon Validation Results", title_justify="left", padding=(0, 1)
        )
        table.add_column("Addon", style="cyan")
        table.add_column("Errors", style="red")
        table.add_column("Warnings", style="yellow")

        for result in results:
            if not result.passed:
                table.add_row(
                    result.addon_name,
                    str(result.error_count),
                    str(result.warning_count),
                )

        console.print(table)

    # Exit code
    if total_failed > 0:
        console.print("\n[bold red]❌ Validation failed[/bold red]")
        raise SystemExit(1)
    else:
        console.print(
            "\n[bold green]✅ All addons validated successfully![/bold green]"
        )
        raise SystemExit(0)
