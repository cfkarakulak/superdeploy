#!/usr/bin/env python3
"""
Domain management commands for SuperDeploy.
Heroku-style domain registration and management.
"""

import click
import yaml
import json
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group(name="domain")
def domain():
    """
    Manage domains for applications.

    Heroku-style domain management for SuperDeploy projects.
    """
    pass


@domain.command(name="add")
@click.option("-p", "--project", required=True, help="Project name")
@click.argument("app_name")
@click.argument("domain")
def add_domain(project: str, app_name: str, domain: str):
    """
    Add a domain to an application.

    Example:
        superdeploy domain:add -p cheapa api api.cheapa.io
        superdeploy domain:add -p cheapa dashboard dashboard.cheapa.io
    """
    try:
        console.print(
            f"\n[bold yellow]▶[/bold yellow] Adding domain [cyan]{domain}[/cyan] to [cyan]{app_name}[/cyan]\n"
        )

        # Load project config
        project_dir = Path.cwd() / "projects" / project
        config_file = project_dir / "project.yml"

        if not config_file.exists():
            console.print(
                f"[red]✗ Project '{project}' not found at {config_file}[/red]"
            )
            raise click.Abort()

        # Read config
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Find app
        apps = config.get("apps", {})
        if app_name not in apps:
            console.print(
                f"[red]✗ App '{app_name}' not found in project '{project}'[/red]"
            )
            console.print(f"Available apps: {', '.join(apps.keys())}")
            raise click.Abort()

        app = apps[app_name]
        vm_role = app.get("vm")

        # Get VM IP from Terraform
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            # Select workspace first
            subprocess.run(
                ["terraform", "workspace", "select", project],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Get outputs
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs = json.loads(result.stdout)
            vms_by_role = outputs.get("vms_by_role", {}).get("value", {})

            # Find VM IP
            vm_ip = None
            role_vms = vms_by_role.get(vm_role, [])
            if role_vms:
                vm_ip = role_vms[0].get("external_ip")

            if not vm_ip:
                console.print(f"[red]✗ Could not find IP for VM role '{vm_role}'[/red]")
                console.print(f"[dim]Available roles: {list(vms_by_role.keys())}[/dim]")
                raise click.Abort()
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to get VM IP from Terraform[/red]")
            console.print(f"[dim]Error: {e.stderr}[/dim]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]✗ Failed to get VM IP: {e}[/red]")
            raise click.Abort()

        # Show DNS instruction
        console.print()
        console.print(
            Panel(
                f"[bold yellow]DNS Configuration Required[/bold yellow]\n\n"
                f"Add the following A record to your DNS:\n\n"
                f"[cyan]Host:[/cyan] {domain}\n"
                f"[cyan]Type:[/cyan] A\n"
                f"[cyan]Value:[/cyan] {vm_ip}\n"
                f"[cyan]TTL:[/cyan] 3600 (or default)\n\n"
                f"[dim]Note: DNS propagation may take a few minutes[/dim]",
                title="📋 DNS Setup",
                border_style="yellow",
            )
        )
        console.print()

        # Ask for confirmation
        if not click.confirm(
            f"Have you added the DNS record for {domain}?", default=False
        ):
            console.print("Aborted. Add the DNS record and try again.")
            raise click.Abort()

        # Update project.yml
        console.print("Updating project.yml...")
        apps[app_name]["domain"] = domain

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓ Updated {config_file}[/green]")

        # Redeploy Caddy addon
        console.print(
            "\n[bold yellow]▶[/bold yellow] Redeploying Caddy with new domain\n"
        )
        console.print("This will update Caddyfile and reload Caddy...")

        # Run superdeploy up with caddy addon only
        result = subprocess.run(
            [
                "superdeploy",
                "up",
                "-p",
                project,
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        # Success message
        console.print()
        console.print(
            Panel(
                f"[bold green]✅ Domain Added Successfully![/bold green]\n\n"
                f"[cyan]App:[/cyan] {app_name}\n"
                f"[cyan]Domain:[/cyan] https://{domain}\n"
                f"[cyan]VM:[/cyan] {vm_ip} ({vm_role})\n\n"
                f"[dim]Caddy will automatically obtain a Let's Encrypt TLS certificate.[/dim]\n"
                f"[dim]Your app is now accessible at: https://{domain}[/dim]",
                title="🎉 Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]✗ Domain add failed: {e}[/red]")
        raise


@domain.command(name="list")
@click.option("-p", "--project", required=True, help="Project name")
def list_domains(project: str):
    """
    List all domains for a project.

    Example:
        superdeploy domain:list -p cheapa
    """
    try:
        # Load project config
        project_dir = Path.cwd() / "projects" / project
        config_file = project_dir / "project.yml"

        if not config_file.exists():
            console.print(f"[red]✗ Project '{project}' not found[/red]")
            raise click.Abort()

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Get VM IPs
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            # Select workspace first
            subprocess.run(
                ["terraform", "workspace", "select", project],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Get outputs
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs = json.loads(result.stdout)
            vms_by_role = outputs.get("vms_by_role", {}).get("value", {})
        except:
            vms_by_role = {}

        # Build table
        table = Table(title=f"Domains for Project: {project}", show_header=True)
        table.add_column("App", style="cyan")
        table.add_column("Domain", style="green")
        table.add_column("VM", style="yellow")
        table.add_column("IP", style="blue")

        apps = config.get("apps", {})
        for app_name, app_config in apps.items():
            domain = app_config.get("domain", "-")
            vm_role = app_config.get("vm", "-")

            # Find VM IP
            vm_ip = "-"
            role_vms = vms_by_role.get(vm_role, [])
            if role_vms:
                vm_ip = role_vms[0].get("external_ip", "-")

            table.add_row(app_name, domain, vm_role, vm_ip)

        console.print()
        console.print(table)
        console.print()

        # Show summary
        total_apps = len(apps)
        apps_with_domains = sum(1 for app in apps.values() if app.get("domain"))
        console.print(
            f"[dim]Total apps: {total_apps} | With domains: {apps_with_domains}[/dim]"
        )
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Failed to list domains: {e}[/red]")
        raise


@domain.command(name="remove")
@click.option("-p", "--project", required=True, help="Project name")
@click.argument("app_name")
def remove_domain(project: str, app_name: str):
    """
    Remove a domain from an application.

    Example:
        superdeploy domain:remove -p cheapa api
    """
    try:
        console.print(
            f"\n[bold yellow]▶[/bold yellow] Removing domain from [cyan]{app_name}[/cyan]\n"
        )

        # Load project config
        project_dir = Path.cwd() / "projects" / project
        config_file = project_dir / "project.yml"

        if not config_file.exists():
            console.print(f"[red]✗ Project '{project}' not found[/red]")
            raise click.Abort()

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        apps = config.get("apps", {})
        if app_name not in apps:
            console.print(f"[red]✗ App '{app_name}' not found[/red]")
            raise click.Abort()

        app = apps[app_name]
        old_domain = app.get("domain")

        if not old_domain:
            console.print(f"App '{app_name}' has no domain configured")
            return

        # Confirm removal
        if not click.confirm(
            f"Remove domain '{old_domain}' from {app_name}?", default=False
        ):
            console.print("Aborted")
            raise click.Abort()

        # Remove domain
        del apps[app_name]["domain"]

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓ Removed domain from {config_file}[/green]")

        # Redeploy Caddy
        console.print("\n[bold yellow]▶[/bold yellow] Redeploying Caddy\n")

        result = subprocess.run(
            [
                "superdeploy",
                "up",
                "-p",
                project,
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        console.print(f"[green]✓ Domain '{old_domain}' removed from {app_name}[/green]")
        console.print("App now accessible via port-based routing only")

    except Exception as e:
        console.print(f"[red]✗ Failed to remove domain: {e}[/red]")
        raise


if __name__ == "__main__":
    domain()
