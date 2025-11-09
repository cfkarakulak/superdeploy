"""
Update firewall rules after port changes
"""

import click
from cli.base import ProjectCommand


class UpdateFirewallCommand(ProjectCommand):
    """Update firewall rules after changing ports in config.yml."""

    def execute(self) -> None:
        """Execute update-firewall command."""
        self.show_header(
            title="Update Firewall Rules",
            project=self.project_name,
            subtitle="Fast firewall update without touching VMs",
        )

        from cli.terraform_utils import (
            get_terraform_dir,
            select_workspace,
            run_terraform_command,
            generate_tfvars,
        )

        # Load config
        try:
            project_config = self.config_service.load_project(self.project_name)
            self.console.print(
                f"[dim]✓ Loaded config: projects/{self.project_name}/config.yml[/dim]"
            )
        except FileNotFoundError as e:
            self.console.print(f"[red]❌ {e}[/red]")
            return
        except ValueError as e:
            self.console.print(f"[red]❌ Invalid configuration: {e}[/red]")
            return

        # Generate tfvars with updated ports
        terraform_dir = get_terraform_dir()
        tfvars_file = generate_tfvars(project_config)
        self.console.print("[dim]✓ Generated tfvars with updated ports[/dim]")

        # Select workspace
        select_workspace(self.project_name, create=False)

        # Apply only firewall changes
        self.console.print(
            "\n[yellow]⚡ Updating firewall rules (this is fast)...[/yellow]"
        )

        try:
            run_terraform_command(
                [
                    "apply",
                    "-target=module.network.google_compute_firewall.allow_app_ports[0]",
                    f"-var-file={tfvars_file}",
                    "-auto-approve",
                ]
            )

            self.console.print(
                "\n[green]✅ Firewall rules updated successfully![/green]"
            )
            self.console.print("\n[bold]📝 What changed:[/bold]")
            self.console.print(
                f"  • Updated allowed ports: {', '.join(project_config.to_terraform_vars()['app_ports'])}"
            )
            self.console.print(
                "\n[dim]Note: VMs were not touched, only firewall rules updated[/dim]"
            )

        except Exception as e:
            self.console.print(f"\n[red]❌ Failed to update firewall: {e}[/red]")
            self.console.print(
                "\n[yellow]💡 Tip: If firewall rule doesn't exist yet, run:[/yellow]"
            )
            self.console.print(f"   [red]superdeploy {self.project_name}:up[/red]")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def update_firewall(project, verbose):
    """
    Update firewall rules after changing ports in config.yml

    This command:
    1. Reads updated ports from config.yml
    2. Updates only the firewall rules (doesn't touch VMs)
    3. Much faster than full terraform apply

    Example:
        # After changing port in config.yml:
        superdeploy cheapa:update-firewall
    """
    cmd = UpdateFirewallCommand(project, verbose=verbose)
    cmd.run()
