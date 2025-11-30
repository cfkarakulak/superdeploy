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
from rich.table import Table
from rich.panel import Panel
from rich.box import ROUNDED

from cli.base import BaseCommand
from cli.ui_components import show_header


class DomainsAddCommand(BaseCommand):
    """Add a domain to an application or orchestrator service."""

    def __init__(
        self,
        project: str,
        app_name: str,
        domain: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.project = project
        self.app_name = app_name
        self.domain = domain

    def execute(self) -> None:
        """Execute add domain command."""
        # Auto-detect orchestrator services by keyword
        ORCHESTRATOR_SERVICES = ["grafana", "prometheus"]
        is_orchestrator = self.app_name in ORCHESTRATOR_SERVICES

        # Validate inputs
        self._validate_inputs(is_orchestrator)

        # Show header
        self._show_header(is_orchestrator)

        # Execute appropriate mode
        if is_orchestrator:
            self._add_orchestrator_domain()
        else:
            self._add_project_domain()

    def _validate_inputs(self, is_orchestrator: bool) -> None:
        """Validate command inputs."""
        if is_orchestrator and self.project:
            self.console.print(
                f"[red]✗ '{self.app_name}' is an orchestrator service[/red]"
            )
            self.console.print(
                f"\n[bold]Usage:[/bold] [cyan]superdeploy orchestrator:domains:add {self.app_name} {self.domain}[/cyan]\n"
            )
            raise click.Abort()

        if not is_orchestrator and not self.project:
            self.console.print(
                f"[red]✗ '{self.app_name}' requires project context[/red]"
            )
            self.console.print(
                f"\n[bold]Usage:[/bold] [cyan]superdeploy <project>:domains:add {self.app_name} {self.domain}[/cyan]"
            )
            self.console.print(
                f"\n[bold]Example:[/bold] [cyan]superdeploy myproject:domains:add {self.app_name} {self.domain}[/cyan]\n"
            )
            raise click.Abort()

    def _show_header(self, is_orchestrator: bool) -> None:
        """Show command header."""
        if is_orchestrator:
            show_header(
                title="Add Domain",
                details={
                    "Service": self.app_name,
                    "Domain": self.domain,
                    "Type": "Orchestrator",
                },
                console=self.console,
            )
        else:
            show_header(
                title="Add Domain",
                project=self.project,
                app=self.app_name,
                details={"Domain": self.domain},
                console=self.console,
            )

    def _add_orchestrator_domain(self) -> None:
        """Add domain to orchestrator service."""
        # Load orchestrator config
        config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
        if not config_file.exists():
            self.console.print(
                f"[red]✗ Orchestrator config not found at {config_file}[/red]"
            )
            self.console.print("Run 'superdeploy orchestrator:init' first")
            raise click.Abort()

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Get orchestrator IP
        vm_ip = self._get_orchestrator_ip()

        # Show DNS instruction and confirm
        self._show_dns_panel(vm_ip)

        if not click.confirm(
            f"Have you added the DNS record for {self.domain}?", default=False
        ):
            self.console.print("Aborted. Add the DNS record and try again.")
            raise click.Abort()

        # Update orchestrator config
        self.console.print("Updating orchestrator config.yml...")
        config[self.app_name]["domain"] = self.domain

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        self.console.print(f"[green]✓ Updated {config_file}[/green]")

        # Redeploy Caddy
        self._redeploy_orchestrator_caddy()

        # Show success message
        self._show_success_panel(vm_ip, "orchestrator")

    def _add_project_domain(self) -> None:
        """Add domain to project app."""
        from cli.database import get_db_session, App, Project

        # Load project from database
        db = get_db_session()
        try:
            # Get project
            project = db.query(Project).filter(Project.name == self.project).first()
            if not project:
                self.console.print(
                    f"[red]✗ Project '{self.project}' not found in database[/red]"
                )
                raise click.Abort()

            # Find app
            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == self.app_name)
                .first()
            )

            if not app:
                # Get available apps
                available_apps = [
                    a.name
                    for a in db.query(App).filter(App.project_id == project.id).all()
                ]
                self.console.print(
                    f"[red]✗ App '{self.app_name}' not found in project '{self.project}'[/red]"
                )
                self.console.print(f"Available apps: {', '.join(available_apps)}")
                raise click.Abort()

            vm_role = app.vm or "app"

            # Get VM IP
            vm_ip = self._get_project_vm_ip(vm_role)

            # Show DNS instruction and confirm
            self._show_dns_panel(vm_ip)

            if not click.confirm(
                f"Have you added the DNS record for {self.domain}?", default=False
            ):
                self.console.print("Aborted. Add the DNS record and try again.")
                raise click.Abort()

            # Update app domain
            self.console.print("Updating app domain in database...")
            app.domain = self.domain
            db.commit()

            self.console.print("[green]✓ Updated app domain[/green]")

        finally:
            db.close()

        # Redeploy Caddy
        self._redeploy_project_caddy()

        # Show success message
        self._show_success_panel(vm_ip, vm_role)

    def _get_orchestrator_ip(self) -> str:
        """Get orchestrator VM IP from Terraform."""
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            subprocess.run(
                ["terraform", "workspace", "select", "orchestrator"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs = json.loads(result.stdout)
            vm_ip = outputs.get("orchestrator_ip", {}).get("value")

            if not vm_ip:
                self.console.print("[red]✗ Could not find orchestrator IP[/red]")
                raise click.Abort()

            return vm_ip
        except Exception as e:
            self.console.print(
                "[red]✗ Failed to get orchestrator IP from Terraform[/red]"
            )
            self.console.print(f"[dim]Error: {e}[/dim]")
            raise click.Abort()

    def _get_project_vm_ip(self, vm_role: str) -> str:
        """Get project VM IP from Terraform."""
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            # Select workspace
            subprocess.run(
                ["terraform", "workspace", "select", self.project],
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
                self.console.print(
                    f"[red]✗ Could not find IP for VM role '{vm_role}'[/red]"
                )
                self.console.print(
                    f"[dim]Available roles: {list(vms_by_role.keys())}[/dim]"
                )
                raise click.Abort()

            return vm_ip
        except subprocess.CalledProcessError as e:
            self.console.print("[red]✗ Failed to get VM IP from Terraform[/red]")
            self.console.print(f"[dim]Error: {e.stderr}[/dim]")
            raise click.Abort()
        except Exception as e:
            self.console.print(f"[red]✗ Failed to get VM IP: {e}[/red]")
            raise click.Abort()

    def _show_dns_panel(self, vm_ip: str) -> None:
        """Show DNS configuration panel."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold yellow]DNS Configuration Required[/bold yellow]\n\n"
                f"Add the following A record to your DNS:\n\n"
                f"[cyan]Host:[/cyan] {self.domain}\n"
                f"[cyan]Type:[/cyan] A\n"
                f"[cyan]Value:[/cyan] {vm_ip}\n"
                f"[cyan]TTL:[/cyan] 3600 (or default)\n\n"
                f"[dim]Note: DNS propagation may take a few minutes[/dim]",
                title="📋 DNS Setup",
                border_style="yellow",
            )
        )
        self.console.print()

    def _redeploy_orchestrator_caddy(self) -> None:
        """Redeploy Caddy on orchestrator."""
        self.console.print(
            "\n[bold yellow]▶[/bold yellow] Redeploying Caddy on orchestrator\n"
        )
        self.console.print("This will update Caddyfile and reload Caddy...")

        result = subprocess.run(
            ["superdeploy", "orchestrator", "up", "--addon", "caddy"],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            self.console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

    def _redeploy_project_caddy(self) -> None:
        """Redeploy Caddy for project."""
        self.console.print(
            "\n[bold yellow]▶[/bold yellow] Redeploying Caddy with new domain\n"
        )
        self.console.print("This will update Caddyfile and reload Caddy...")

        result = subprocess.run(
            [
                "superdeploy",
                f"{self.project}:up",
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            self.console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

    def _show_success_panel(self, vm_ip: str, vm_info: str) -> None:
        """Show success panel."""
        self.console.print()
        self.console.print(
            Panel(
                f"[color(248)]Domain added successfully.[/color(248)]\n"
                f"[cyan]{'Service' if vm_info == 'orchestrator' else 'App'}:[/cyan] {self.app_name}\n"
                f"[cyan]Domain:[/cyan] https://{self.domain}\n"
                f"[cyan]VM:[/cyan] {vm_ip} ({vm_info})\n\n"
                f"[dim]Caddy will automatically obtain a Let's Encrypt TLS certificate.[/dim]\n"
                f"[dim]Your {'service' if vm_info == 'orchestrator' else 'app'} is now accessible at: https://{self.domain}[/dim]",
                title="🎉 Success",
                border_style="green",
            )
        )


class DomainsListCommand(BaseCommand):
    """List all domains (orchestrator + all projects)."""

    def __init__(
        self, project: str = None, verbose: bool = False, json_output: bool = False
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.project = project

    def execute(self) -> None:
        """Execute list domains command."""
        # JSON output mode - simplified
        if self.json_output:
            self.output_json(
                {
                    "status": "completed",
                    "message": "Use normal mode for detailed domain listing",
                    "filter": self.project if self.project else "all",
                }
            )
            return

        # Show header
        if self.project:
            show_header(
                title="Domain List",
                project=self.project,
                console=self.console,
            )
        else:
            show_header(
                title="Domain List",
                subtitle="All domains across orchestrator and projects",
                console=self.console,
            )

        # Get projects to show
        projects_to_show = self._get_projects_to_show()

        # Build unified table
        main_table = self._build_domains_table()

        # Add orchestrator domains (if showing all)
        if not self.project:
            self._add_orchestrator_domains_to_table(main_table)

        # Add project domains
        self._add_project_domains_to_table(main_table, projects_to_show)

        # Display table
        self.console.print()
        self.console.print(main_table)
        self.console.print()

    def _get_projects_to_show(self) -> list[str]:
        """Get list of projects to display."""
        projects_dir = Path.cwd() / "projects"
        all_projects = (
            [
                d.name
                for d in projects_dir.iterdir()
                if d.is_dir() and (d / "config.yml").exists()
            ]
            if projects_dir.exists()
            else []
        )

        # If -p specified, show only that project
        if self.project:
            if self.project not in all_projects:
                self.console.print(f"[red]✗ Project '{self.project}' not found[/red]")
                raise click.Abort()
            return [self.project]

        return all_projects

    def _build_domains_table(self) -> Table:
        """Build the domains table structure."""
        table = Table(
            title="[bold white]All Domains[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Type", style="cyan", width=15)
        table.add_column("Service/App", style="yellow", width=20)
        table.add_column("Domain", style="green", width=30)
        table.add_column("VM/Role", style="magenta", width=15)
        table.add_column("IP", style="blue")
        return table

    def _add_orchestrator_domains_to_table(self, table: Table) -> None:
        """Add orchestrator domains to table."""
        config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
        if not config_file.exists():
            return

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Get orchestrator IP
        vm_ip = self._get_orchestrator_ip()

        # Add orchestrator section header
        table.add_row("[bold yellow]Orchestrator[/bold yellow]", "", "", "", "")

        # Add services
        services = ["grafana", "prometheus"]
        for service in services:
            service_config = config.get(service, {})
            domain = service_config.get("domain", "") or "-"
            table.add_row("  Service", f"  {service}", domain, "orchestrator", vm_ip)

    def _add_project_domains_to_table(self, table: Table, projects: list[str]) -> None:
        """Add project domains to table."""
        terraform_dir = Path.cwd() / "shared" / "terraform"

        for proj_name in projects:
            project_dir = Path.cwd() / "projects" / proj_name
            config_file = project_dir / "config.yml"

            if not config_file.exists():
                continue

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Get VM IPs for this project
            vms_by_role = self._get_project_vms(proj_name, terraform_dir)

            # Add project section header
            table.add_row(
                f"[bold yellow]Project: {proj_name.title()}[/bold yellow]",
                "",
                "",
                "",
                "",
            )

            # Add apps
            apps = config.get("apps", {})
            for app_name, app_config in apps.items():
                domain = app_config.get("domain", "") or "-"
                vm_role = app_config.get("vm", "-")

                # Find VM IP
                vm_ip = "-"
                role_vms = vms_by_role.get(vm_role, [])
                if role_vms:
                    vm_ip = role_vms[0].get("external_ip", "-")

                table.add_row("  App", f"  {app_name}", domain, vm_role, vm_ip)

    def _get_orchestrator_ip(self) -> str:
        """Get orchestrator IP from Terraform."""
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            subprocess.run(
                ["terraform", "workspace", "select", "orchestrator"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs = json.loads(result.stdout)
            return outputs.get("orchestrator_ip", {}).get("value", "-")
        except:
            return "-"

    def _get_project_vms(self, project_name: str, terraform_dir: Path) -> dict:
        """Get VMs by role for a project."""
        try:
            # Select workspace
            subprocess.run(
                ["terraform", "workspace", "select", project_name],
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
            return outputs.get("vms_by_role", {}).get("value", {})
        except:
            return {}


class DomainsRemoveCommand(BaseCommand):
    """Remove a domain from an application or orchestrator service."""

    def __init__(
        self,
        project: str,
        app_name: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.project = project
        self.app_name = app_name

    def execute(self) -> None:
        """Execute remove domain command."""
        # Auto-detect orchestrator services by keyword
        ORCHESTRATOR_SERVICES = ["grafana", "prometheus"]
        is_orchestrator = self.app_name in ORCHESTRATOR_SERVICES

        # Validate inputs
        self._validate_inputs(is_orchestrator)

        # Show header
        self._show_header(is_orchestrator)

        # Execute appropriate mode
        if is_orchestrator:
            self._remove_orchestrator_domain()
        else:
            self._remove_project_domain()

    def _validate_inputs(self, is_orchestrator: bool) -> None:
        """Validate command inputs."""
        if is_orchestrator and self.project:
            self.console.print(
                f"[red]✗ '{self.app_name}' is an orchestrator service[/red]"
            )
            self.console.print(
                f"\n[bold]Usage:[/bold] [cyan]superdeploy orchestrator:domains:remove {self.app_name}[/cyan]\n"
            )
            raise click.Abort()

        if not is_orchestrator and not self.project:
            self.console.print(
                f"[red]✗ '{self.app_name}' requires project context[/red]"
            )
            self.console.print(
                f"\n[bold]Usage:[/bold] [cyan]superdeploy <project>:domains:remove {self.app_name}[/cyan]"
            )
            self.console.print(
                f"\n[bold]Example:[/bold] [cyan]superdeploy myproject:domains:remove {self.app_name}[/cyan]\n"
            )
            raise click.Abort()

    def _show_header(self, is_orchestrator: bool) -> None:
        """Show command header."""
        if is_orchestrator:
            show_header(
                title="Remove Domain",
                details={"Service": self.app_name, "Type": "Orchestrator"},
                console=self.console,
            )
        else:
            show_header(
                title="Remove Domain",
                project=self.project,
                app=self.app_name,
                console=self.console,
            )

    def _remove_orchestrator_domain(self) -> None:
        """Remove domain from orchestrator service."""
        # Load orchestrator config
        config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
        if not config_file.exists():
            self.console.print("[red]✗ Orchestrator config not found[/red]")
            raise click.Abort()

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        service_config = config.get(self.app_name, {})
        old_domain = service_config.get("domain")

        if not old_domain:
            self.console.print(
                f"[yellow]Service '{self.app_name}' has no domain configured[/yellow]"
            )
            return

        # Confirm removal
        if not click.confirm(
            f"Remove domain '{old_domain}' from {self.app_name}?", default=False
        ):
            self.console.print("Aborted")
            raise click.Abort()

        # Remove domain (set to empty string)
        config[self.app_name]["domain"] = ""

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        self.console.print(f"[green]✓ Removed domain from {config_file}[/green]")

        # Redeploy Caddy on orchestrator
        self.console.print(
            "\n[bold yellow]▶[/bold yellow] Redeploying Caddy on orchestrator\n"
        )

        result = subprocess.run(
            ["superdeploy", "orchestrator", "up", "--addon", "caddy"],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            self.console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        self.console.print(
            f"[green]✓ Domain '{old_domain}' removed from {self.app_name}[/green]"
        )
        self.console.print("Service now accessible via port-based routing only")

    def _remove_project_domain(self) -> None:
        """Remove domain from project app."""
        from cli.database import get_db_session, App, Project

        # Load project from database
        db = get_db_session()
        try:
            # Get project
            project = db.query(Project).filter(Project.name == self.project).first()
            if not project:
                self.console.print(
                    f"[red]✗ Project '{self.project}' not found in database[/red]"
                )
                raise click.Abort()

            # Get app
            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == self.app_name)
                .first()
            )

            if not app:
                self.console.print(f"[red]✗ App '{self.app_name}' not found[/red]")
                raise click.Abort()

            old_domain = app.domain

            if not old_domain:
                self.console.print(
                    f"[yellow]App '{self.app_name}' has no domain configured[/yellow]"
                )
                return

            # Confirm removal
            if not click.confirm(
                f"Remove domain '{old_domain}' from {self.app_name}?", default=False
            ):
                self.console.print("Aborted")
                raise click.Abort()

            # Remove domain
            app.domain = None
            db.commit()

            self.console.print("[green]✓ Removed domain from app[/green]")

        finally:
            db.close()

        # Redeploy Caddy
        self.console.print("\n[bold yellow]▶[/bold yellow] Redeploying Caddy\n")

        result = subprocess.run(
            [
                "superdeploy",
                "up",
                "-p",
                self.project,
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            self.console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        self.console.print(
            f"[green]✓ Domain '{old_domain}' removed from {self.app_name}[/green]"
        )
        self.console.print("App now accessible via port-based routing only")


# Click command wrappers
@click.command(name="domains:add")
@click.option("-p", "--project", help="Project name (required for app domains)")
@click.argument("app_name")
@click.argument("domain")
def domains_add(project: str, app_name: str, domain: str):
    """
    Add a domain to an application or orchestrator service.

    Orchestrator services (grafana, prometheus) are auto-detected.
    Project apps use namespace syntax.

    Examples:
    # Orchestrator services (keyword-based)
    superdeploy orchestrator:domains:add grafana grafana.cheapa.io
    superdeploy orchestrator:domains:add prometheus prometheus.cheapa.io

    # Project apps (namespace syntax - NEW!)
    superdeploy cheapa:domains:add api api.cheapa.io
    superdeploy cheapa:domains:add dashboard dashboard.cheapa.io
    """
    cmd = DomainsAddCommand(project=project, app_name=app_name, domain=domain)
    cmd.run()


@click.command(name="domains:list")
@click.option("-p", "--project", help="Project name (show only this project)")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def domains_list(project: str, json_output: bool):
    """
    List all domains (orchestrator + all projects).

    By default shows ALL domains. Use namespace syntax to filter by project.

    Examples:
        superdeploy domains:list                  # all domains
        superdeploy cheapa:domains:list           # only cheapa project
    """
    cmd = DomainsListCommand(project=project, json_output=json_output)
    cmd.run()


@click.command(name="domains:remove")
@click.option("-p", "--project", help="Project name (required for app domains)")
@click.argument("app_name")
def domains_remove(project: str, app_name: str):
    """
    Remove a domain from an application or orchestrator service.

    Orchestrator services (grafana, prometheus) are auto-detected.
    Project apps use namespace syntax.

    Examples:
        superdeploy orchestrator:domains:remove grafana   # orchestrator
        superdeploy cheapa:domains:remove api            # project app
    """
    cmd = DomainsRemoveCommand(project=project, app_name=app_name)
    cmd.run()
