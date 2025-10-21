"""
Project initialization command with interactive setup
"""

import os
import yaml
import click
import ipaddress
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from jinja2 import Template
import secrets

console = Console()


def get_used_subnets():
    """Get list of subnets already in use by other projects"""
    used_subnets = []
    projects_dir = Path("/opt/apps")
    
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                config_file = project_dir / "config.yml"
                if config_file.exists():
                    with open(config_file) as f:
                        config = yaml.safe_load(f)
                        if config and "network" in config and "subnet" in config["network"]:
                            used_subnets.append(config["network"]["subnet"])
    
    return used_subnets


def find_next_subnet(used_subnets):
    """Find next available subnet starting from 172.20.0.0/24"""
    base = ipaddress.IPv4Network("172.20.0.0/24")
    
    # Try subnets incrementally
    for i in range(20, 255):  # 172.20.0.0 to 172.254.0.0
        candidate = ipaddress.IPv4Network(f"172.{i}.0.0/24")
        if str(candidate) not in used_subnets:
            return str(candidate)
    
    raise ValueError("No available subnets in 172.x.0.0/24 range")


def render_template(template_path, context):
    """Render a template file with given context"""
    with open(template_path) as f:
        template = Template(f.read())
    
    # Render template with context
    return template.render(**context)


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--yes", "-y", is_flag=True, help="Accept all defaults")
@click.option("--subnet", help="Custom subnet (e.g., 172.21.0.0/24)")
@click.option("--services", help="Comma-separated services (e.g., api,dashboard)")
@click.option("--no-interactive", is_flag=True, help="Disable interactive mode")
def init(project, yes, subnet, services, no_interactive):
    """
    Initialize a new project with interactive setup
    
    Example:
        superdeploy init -p marketplace
    """
    console.print(f"\n[bold cyan]🎯 Creating new project: {project}[/bold cyan]")
    console.print("━" * 40)
    
    # Check if project already exists
    project_dir = Path(f"/opt/apps/{project}")
    if project_dir.exists():
        console.print(f"[red]❌ Project '{project}' already exists![/red]")
        return
    
    # Determine mode
    interactive = not no_interactive and not yes
    
    # Service selection
    available_services = ["api", "dashboard", "services", "worker", "scraper"]
    selected_services = []
    
    if services:
        selected_services = [s.strip() for s in services.split(",")]
    elif interactive:
        console.print("\n[bold]Select services for this project:[/bold]")
        for service in available_services:
            if service in ["api", "dashboard", "services"]:  # Default selections
                selected = Confirm.ask(f"  Include {service}?", default=True)
            else:
                selected = Confirm.ask(f"  Include {service}?", default=False)
            
            if selected:
                selected_services.append(service)
    else:
        # Default services
        selected_services = ["api", "dashboard", "services"]
    
    # Network configuration
    used_subnets = get_used_subnets()
    
    if subnet:
        project_subnet = subnet
    elif interactive:
        console.print("\n[bold]Configure networking:[/bold]")
        auto_subnet = Confirm.ask("  Auto-assign subnet?", default=True)
        
        if auto_subnet:
            project_subnet = find_next_subnet(used_subnets)
            console.print(f"\n[green]✨ Auto-assigned subnet: {project_subnet}[/green]")
        else:
            project_subnet = Prompt.ask("  Enter custom subnet", default="172.20.0.0/24")
    else:
        project_subnet = find_next_subnet(used_subnets)
    
    # Database configuration
    generate_passwords = True
    if interactive:
        console.print("\n[bold]Database configuration:[/bold]")
        generate_passwords = Confirm.ask(
            "  Generate secure passwords?", 
            default=True
        )
    
    # Monitoring
    enable_monitoring = True
    if interactive:
        enable_monitoring = Confirm.ask("\nEnable monitoring for this project?", default=True)
    
    # Domain
    project_domain = ""
    if interactive:
        console.print("\n[bold]Configure domain (optional):[/bold]")
        project_domain = Prompt.ask(
            f"  Domain for {project}", 
            default=f"{project}.example.com"
        )
        if project_domain == f"{project}.example.com":
            project_domain = ""  # Don't save example domain
    
    # Port assignments
    api_port = 8000 + len(used_subnets) * 10  # Offset ports by project
    dashboard_port = 3000 + len(used_subnets) * 10
    
    # Summary
    console.print("\n[bold cyan]📋 Summary:[/bold cyan]")
    console.print("━" * 40)
    
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="dim")
    table.add_column("Value", style="bright_white")
    
    table.add_row("Project:", project)
    table.add_row("Services:", ", ".join(selected_services))
    table.add_row("Network:", project_subnet)
    table.add_row("Database:", "PostgreSQL 15")
    table.add_row("Queue:", "RabbitMQ 3.12")
    table.add_row("Cache:", "Redis 7")
    table.add_row("Monitoring:", "✓ Enabled" if enable_monitoring else "✗ Disabled")
    if project_domain:
        table.add_row("Domain:", project_domain)
    
    console.print(table)
    
    # Confirm
    if interactive and not Confirm.ask("\n[bold]Create project?[/bold]", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return
    
    # Create project structure
    console.print("\n[dim]Creating project structure...[/dim]")
    
    # Template context
    context = {
        "PROJECT": project,
        "DESCRIPTION": f"{project.title()} project",
        "CREATED_AT": datetime.now().isoformat(),
        "UPDATED_AT": datetime.now().isoformat(),
        "SUBNET": project_subnet,
        "SERVICES_LIST": selected_services,  # For Jinja2 templates
        "POSTGRES_VERSION": "15-alpine",
        "RABBITMQ_VERSION": "3.12-management-alpine",
        "REDIS_VERSION": "7-alpine",
        "API_PORT": api_port,
        "DASHBOARD_PORT": dashboard_port,
        "MONITORING_ENABLED": enable_monitoring,
        "PROMETHEUS_TARGET": enable_monitoring,
        "DOMAIN": project_domain,
    }
    
    # Create directories
    compose_dir = project_dir / "compose"
    data_dir = project_dir / "data"
    
    compose_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy and render templates
    template_dir = Path(__file__).parent.parent.parent / "templates"
    
    # Render docker-compose.core.yml
    core_template = template_dir / "compose" / "docker-compose.core.yml"
    core_output = compose_dir / "docker-compose.core.yml"
    core_output.write_text(render_template(core_template, context))
    
    # Render docker-compose.apps.yml
    apps_template = template_dir / "compose" / "docker-compose.apps.yml"
    apps_output = compose_dir / "docker-compose.apps.yml"
    apps_output.write_text(render_template(apps_template, context))
    
    # Render project config
    config_template = template_dir / "project-config.yml"
    config_output = project_dir / "config.yml"
    config_output.write_text(render_template(config_template, context))
    
    # Generate passwords if requested
    passwords = {}
    if generate_passwords:
        passwords = {
            "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
            "RABBITMQ_PASSWORD": secrets.token_urlsafe(32),
            "REDIS_PASSWORD": secrets.token_urlsafe(32),
        }
        
        # Save password hints
        password_file = project_dir / ".passwords.yml"
        with open(password_file, "w") as f:
            yaml.dump({
                "generated_at": datetime.now().isoformat(),
                "passwords": passwords,
                "note": "Add these to GitHub Secrets for each app repository"
            }, f)
        
        # Make it readable only by owner
        os.chmod(password_file, 0o600)
    
    # Success message
    console.print(f"\n[green]✅ Project created successfully![/green]")
    
    # Next steps
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("1. Add secrets to GitHub:")
    
    for service in selected_services:
        if service in ["api", "dashboard", "services"]:
            console.print(f"   [dim]gh secret set POSTGRES_PASSWORD -R {project}io/{service}[/dim]")
            console.print(f"   [dim]gh secret set RABBITMQ_PASSWORD -R {project}io/{service}[/dim]")
            console.print(f"   [dim]gh secret set REDIS_PASSWORD -R {project}io/{service}[/dim]")
            break
    
    if passwords:
        console.print(f"\n   [dim]Generated passwords saved in: /opt/apps/{project}/.passwords.yml[/dim]")
    
    console.print("\n2. Push your code:")
    console.print("   [dim]git push origin production[/dim]")
    
    console.print("\n[green]🚀 That's it! Deployment will happen automatically.[/green]")


if __name__ == "__main__":
    init()