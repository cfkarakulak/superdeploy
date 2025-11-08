"""SuperDeploy CLI - Doctor command (Refactored)"""

import click
import subprocess
from rich.table import Table
from cli.base import BaseCommand
from cli.services import ConfigService, StateService
from cli.constants import REQUIRED_TOOLS


class DoctorCommand(BaseCommand):
    """System health check and diagnostics."""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.table = Table(
            title="System Health Report", title_justify="left", padding=(0, 1)
        )
        self.table.add_column("Check", style="cyan", no_wrap=True)
        self.table.add_column("Status")
        self.table.add_column("Details", style="dim")

    def check_tool(self, tool_name: str) -> bool:
        """Check if a tool is installed."""
        try:
            subprocess.run(["which", tool_name], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def check_auth(self, check_cmd: str) -> tuple[bool, str]:
        """Check if a tool is authenticated."""
        try:
            result = subprocess.run(
                check_cmd.split(), check=True, capture_output=True, text=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError:
            return False, ""

    def check_tools(self) -> None:
        """Check required tools installation."""
        self.console.print("\n[cyan]━━━ Checking Tools ━━━[/cyan]")

        for tool in REQUIRED_TOOLS:
            if self.check_tool(tool):
                self.table.add_row(f"✅ {tool}", "[green]Installed[/green]", "")
            else:
                self.table.add_row(
                    f"❌ {tool}", "[red]Missing[/red]", f"brew install {tool}"
                )

    def check_authentication(self) -> None:
        """Check authentication status."""
        self.console.print("[cyan]━━━ Checking Authentication ━━━[/cyan]")

        # GCloud
        gcloud_ok, gcloud_project = self.check_auth("gcloud config get-value project")
        if gcloud_ok and gcloud_project:
            self.table.add_row(
                "✅ GCloud auth", "[green]OK[/green]", f"Project: {gcloud_project}"
            )
        else:
            self.table.add_row(
                "❌ GCloud auth",
                "[red]Not authenticated[/red]",
                "Run: gcloud auth login",
            )

        # GitHub CLI
        gh_ok, _ = self.check_auth("gh auth status")
        if gh_ok:
            self.table.add_row("✅ GitHub CLI", "[green]Authenticated[/green]", "")
        else:
            self.table.add_row(
                "❌ GitHub CLI", "[red]Not authenticated[/red]", "Run: gh auth login"
            )

    def check_configuration(self) -> list[str]:
        """Check project configuration. Returns list of projects."""
        self.console.print("[cyan]━━━ Checking Configuration ━━━[/cyan]")

        config_service = ConfigService(self.project_root)
        projects = config_service.list_projects()

        if not projects:
            self.table.add_row(
                "⏳ Projects",
                "[yellow]None found[/yellow]",
                "Run: superdeploy myproject:init",
            )
            return []

        self.table.add_row(
            "✅ Projects", "[green]Found[/green]", f"{len(projects)} project(s)"
        )

        # Validate first project
        first_project = projects[0]
        try:
            config_service.validate_project(first_project)
            self.table.add_row(
                f"  ✅ {first_project}", "[green]Valid config[/green]", ""
            )
        except Exception as e:
            self.table.add_row(
                f"  ❌ {first_project}", "[red]Invalid config[/red]", str(e)[:30]
            )

        return projects

    def check_infrastructure(self, projects: list[str]) -> None:
        """Check infrastructure deployment status."""
        self.console.print("[cyan]━━━ Checking Infrastructure ━━━[/cyan]")

        # Check orchestrator
        self._check_orchestrator()

        # Check project VMs
        if projects:
            self._check_project_vms(projects[0])

    def _check_orchestrator(self) -> None:
        """Check orchestrator status."""
        from cli.core.orchestrator_loader import OrchestratorLoader

        try:
            orch_loader = OrchestratorLoader(self.project_root / "shared")
            orch_config = orch_loader.load()

            if orch_config.is_deployed():
                orch_ip = orch_config.get_ip()
                if orch_ip:
                    # Try to ping
                    try:
                        subprocess.run(
                            ["ping", "-c", "1", "-W", "2", orch_ip],
                            check=True,
                            capture_output=True,
                        )
                        self.table.add_row(
                            "✅ Orchestrator", "[green]Reachable[/green]", orch_ip
                        )
                    except subprocess.CalledProcessError:
                        self.table.add_row(
                            "❌ Orchestrator", "[red]Unreachable[/red]", orch_ip
                        )
                else:
                    self.table.add_row(
                        "⏳ Orchestrator", "[yellow]IP not found[/yellow]", ""
                    )
            else:
                self.table.add_row(
                    "⏳ Orchestrator",
                    "[yellow]Not deployed[/yellow]",
                    "Run: superdeploy orchestrator up",
                )
        except Exception:
            self.table.add_row("⏳ Orchestrator", "[yellow]Not configured[/yellow]", "")

    def _check_project_vms(self, project_name: str) -> None:
        """Check project VM deployment status."""
        try:
            state_service = StateService(self.project_root, project_name)

            if state_service.has_state():
                vm_ips = state_service.get_all_vm_ips()
                self.table.add_row(
                    f"✅ {project_name} VMs",
                    "[green]Deployed[/green]",
                    f"{len(vm_ips)} VM(s)",
                )
            else:
                self.table.add_row(
                    f"⏳ {project_name} VMs",
                    "[yellow]Not deployed[/yellow]",
                    f"Run: superdeploy {project_name}:up",
                )
        except Exception:
            self.table.add_row(
                f"⏳ {project_name} VMs",
                "[yellow]Not deployed[/yellow]",
                f"Run: superdeploy {project_name}:up",
            )

    def execute(self) -> None:
        """Execute doctor command."""
        self.show_header(
            title="System Diagnostics",
            subtitle="Running comprehensive health check of tools and configuration",
        )

        # Run all checks
        self.check_tools()
        self.check_authentication()
        projects = self.check_configuration()
        self.check_infrastructure(projects)

        # Display results
        self.console.print("\n")
        self.console.print(self.table)

        # Summary
        self.console.print("\n[bold cyan]━━━ Summary ━━━[/bold cyan]")
        self.print_success("Diagnostics complete! Review results above.")


@click.command()
def doctor():
    """
    Health check & diagnostics

    Checks:
    - Required tools installation
    - Authentication status
    - Configuration validity
    - VM connectivity
    """
    cmd = DoctorCommand(verbose=False)
    cmd.run()
