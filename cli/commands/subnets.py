"""SuperDeploy CLI - Subnets command (View subnet allocations)"""

import click
from rich.table import Table
from cli.base import BaseCommand
from cli.subnet_allocator import SubnetAllocator


class SubnetsCommand(BaseCommand):
    """View subnet allocations for all projects."""

    def execute(self) -> None:
        """Execute subnets command."""
        allocator = SubnetAllocator()
        allocations = allocator.list_allocations()

        # JSON output mode
        if self.json_output:
            subnets_data = {"orchestrator": SubnetAllocator.get_orchestrator_subnet()}
            for project_name in sorted(allocations.keys()):
                subnets_data[project_name] = allocations[project_name]

            self.output_json(
                {
                    "subnets": subnets_data,
                    "total_projects": len(allocations),
                    "available_slots": 255 - len(allocations),
                }
            )
            return

        self.show_header(
            title="Subnet Allocations",
            subtitle="View subnet CIDR allocations for all projects",
        )

        if not allocations:
            self.console.print("[yellow]No subnet allocations found.[/yellow]")
            self.console.print(
                "[dim]Subnets are allocated automatically when projects are deployed.[/dim]\n"
            )
            return

        # Create table
        table = Table(
            title="Subnet Allocations",
            show_header=True,
            header_style="bold cyan",
            title_justify="left",
            padding=(0, 1),
        )
        table.add_column("Project", style="white", no_wrap=True)
        table.add_column("Subnet CIDR", style="green")
        table.add_column("IP Range", style="dim")

        # Add orchestrator (reserved)
        orch_subnet = SubnetAllocator.get_orchestrator_subnet()
        table.add_row("orchestrator", orch_subnet, "[dim]Reserved[/dim]")

        # Add project allocations
        for project_name in sorted(allocations.keys()):
            subnet = allocations[project_name]
            # Calculate IP range (e.g., 10.1.0.0/16 -> 10.1.0.1 - 10.1.255.254)
            parts = subnet.split("/")
            if len(parts) == 2:
                base_ip = parts[0]
                ip_parts = base_ip.split(".")
                if len(ip_parts) == 4:
                    # For /16 subnet: X.Y.0.0/16 -> X.Y.0.1 - X.Y.255.254
                    start_ip = f"{ip_parts[0]}.{ip_parts[1]}.0.1"
                    end_ip = f"{ip_parts[0]}.{ip_parts[1]}.255.254"
                    ip_range = f"{start_ip} - {end_ip}"
                else:
                    ip_range = "N/A"
            else:
                ip_range = "N/A"

            table.add_row(project_name, subnet, ip_range)

        self.console.print(table)
        self.console.print(f"\n[dim]Total projects: {len(allocations)}[/dim]")
        self.console.print(f"[dim]Available slots: {255 - len(allocations)}[/dim]\n")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def subnets(verbose, json_output):
    """
    View subnet allocations for all projects

    Shows which subnet CIDR is allocated to each project to avoid conflicts.
    """
    cmd = SubnetsCommand(verbose=verbose, json_output=json_output)
    cmd.run()
