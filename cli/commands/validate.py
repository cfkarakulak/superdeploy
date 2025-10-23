"""SuperDeploy CLI - Validate command"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from cli.utils import get_project_path, validate_project
import yaml

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
def validate(project):
    """
    Validate project configuration

    \b
    Examples:
      superdeploy validate -p cheapa
    
    \b
    This command validates:
    - config.yml structure and required fields
    - Port assignments (no conflicts)
    - Service definitions
    - Repository URLs
    - Network configuration
    """
    console.print(
        Panel.fit(
            f"[bold cyan]🔍 Validating Project Configuration[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]",
            border_style="cyan",
        )
    )

    # Validate project exists
    try:
        validate_project(project)
        project_path = get_project_path(project)
    except Exception as e:
        console.print(f"[red]❌ Project validation failed: {e}[/red]")
        raise SystemExit(1)

    # Load config
    config_file = project_path / "config.yml"
    
    if not config_file.exists():
        console.print(f"[red]❌ Config file not found: {config_file}[/red]")
        raise SystemExit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    errors = []
    warnings = []
    
    # Validation checks
    console.print("\n[bold]Running validation checks...[/bold]\n")

    # 1. Required fields
    required_fields = ["project", "services", "ports", "core_services", "github"]
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
                    errors.append(f"Port conflict: {ext_port} used by multiple services")
                external_ports.append(ext_port)
        
        console.print(f"[green]✓[/green] Port assignments: {len(external_ports)} ports")

    # 4. Core services
    if "core_services" in config:
        required_core = ["postgres", "rabbitmq", "redis"]
        for core in required_core:
            if core not in config["core_services"]:
                warnings.append(f"Core service '{core}' not configured")
            else:
                console.print(f"[green]✓[/green] Core service: {core}")

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
        table = Table(title="Configuration Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Project", config.get("project", "N/A"))
        table.add_row("Services", str(len(config.get("services", []))))
        table.add_row("Ports", str(len(config.get("ports", {}))))
        table.add_row("Core Services", str(len(config.get("core_services", {}))))
        table.add_row("Repositories", str(len(config.get("github", {}).get("repositories", {}))))
        
        console.print()
        console.print(table)
        
        raise SystemExit(0)
    elif errors:
        console.print("[bold red]❌ Validation failed with errors[/bold red]")
        raise SystemExit(1)
    else:
        console.print("[bold yellow]⚠️  Validation passed with warnings[/bold yellow]")
        raise SystemExit(0)
