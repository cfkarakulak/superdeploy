"""SuperDeploy CLI - Doctor command"""

import click
import subprocess
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header

console = Console()


def check_tool(tool_name):
    """Check if a tool is installed"""
    try:
        subprocess.run(["which", tool_name], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def check_auth(tool_name, check_cmd):
    """Check if a tool is authenticated"""
    try:
        result = subprocess.run(
            check_cmd.split(), check=True, capture_output=True, text=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError:
        return False, None


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
    show_header(
        title="System Diagnostics",
        subtitle="Running comprehensive health check of tools and configuration",
        console=console,
    )

    # Create table
    table = Table(title="System Health Report", title_justify="left", padding=(0, 1))
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Details", style="dim")

    # 1. Check required tools
    console.print("\n[cyan]━━━ Checking Tools ━━━[/cyan]")

    required_tools = [
        "python3",
        "terraform",
        "ansible",
        "gcloud",
        "jq",
        "gh",
        "age",
        "ssh",
    ]

    for tool in required_tools:
        if check_tool(tool):
            table.add_row(f"✅ {tool}", "[green]Installed[/green]", "")
        else:
            table.add_row(f"❌ {tool}", "[red]Missing[/red]", f"brew install {tool}")

    # 2. Check authentication
    console.print("[cyan]━━━ Checking Authentication ━━━[/cyan]")

    # GCloud
    gcloud_ok, gcloud_project = check_auth("gcloud", "gcloud config get-value project")
    if gcloud_ok and gcloud_project:
        table.add_row(
            "✅ GCloud auth", "[green]OK[/green]", f"Project: {gcloud_project}"
        )
    else:
        table.add_row(
            "❌ GCloud auth", "[red]Not authenticated[/red]", "Run: gcloud auth login"
        )

    # GitHub CLI
    gh_ok, gh_user = check_auth("gh", "gh auth status")
    if gh_ok:
        table.add_row("✅ GitHub CLI", "[green]Authenticated[/green]", "")
    else:
        table.add_row(
            "❌ GitHub CLI", "[red]Not authenticated[/red]", "Run: gh auth login"
        )

    # 3. Check configuration
    console.print("[cyan]━━━ Checking Configuration ━━━[/cyan]")

    # Check if any projects exist
    from cli.utils import get_project_root

    project_root = get_project_root()
    projects_dir = project_root / "projects"

    if projects_dir.exists():
        projects = [
            d.name
            for d in projects_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and (d / "project.yml").exists()
        ]

        if projects:
            table.add_row(
                "✅ Projects", "[green]Found[/green]", f"{len(projects)} project(s)"
            )

            # Check first project as example
            first_project = projects[0]
            from cli.core.config_loader import ConfigLoader

            try:
                config_loader = ConfigLoader(projects_dir)
                project_config = config_loader.load_project(first_project)
                table.add_row(
                    f"  ✅ {first_project}", "[green]Valid config[/green]", ""
                )
            except Exception as e:
                table.add_row(
                    f"  ❌ {first_project}", "[red]Invalid config[/red]", str(e)[:30]
                )
        else:
            table.add_row(
                "⏳ Projects",
                "[yellow]None found[/yellow]",
                "Run: superdeploy init -p myproject",
            )
    else:
        table.add_row(
            "⏳ Projects",
            "[yellow]None found[/yellow]",
            "Run: superdeploy init -p myproject",
        )

    # 4. Check VMs (if deployed)
    console.print("[cyan]━━━ Checking Infrastructure ━━━[/cyan]")

    # Check orchestrator
    from cli.core.orchestrator_loader import OrchestratorLoader

    try:
        orch_loader = OrchestratorLoader(project_root / "shared")
        orch_config = orch_loader.load()

        if orch_config.is_deployed():
            orch_ip = orch_config.get_ip()
            if orch_ip:
                # Try to ping orchestrator
                try:
                    subprocess.run(
                        ["ping", "-c", "1", "-W", "2", orch_ip],
                        check=True,
                        capture_output=True,
                    )
                    table.add_row(
                        "✅ Orchestrator", "[green]Reachable[/green]", orch_ip
                    )
                except subprocess.CalledProcessError:
                    table.add_row("❌ Orchestrator", "[red]Unreachable[/red]", orch_ip)
            else:
                table.add_row("⏳ Orchestrator", "[yellow]IP not found[/yellow]", "")
        else:
            table.add_row(
                "⏳ Orchestrator",
                "[yellow]Not deployed[/yellow]",
                "Run: [red]superdeploy orchestrator up[/red]",
            )
    except Exception:
        table.add_row("⏳ Orchestrator", "[yellow]Not configured[/yellow]", "")

    # Check project VMs if projects exist
    if projects_dir.exists() and projects:
        first_project = projects[0]
        try:
            
            env = load_env(project=first_project)

            # Check for any VM IPs
            vm_ips = {k: v for k, v in env.items() if k.endswith("_EXTERNAL_IP")}

            if vm_ips:
                table.add_row(
                    f"✅ {first_project} VMs",
                    "[green]Deployed[/green]",
                    f"{len(vm_ips)} VM(s)",
                )
            else:
                table.add_row(
                    f"⏳ {first_project} VMs",
                    "[yellow]Not deployed[/yellow]",
                    f"Run: [red]superdeploy up -p {first_project}[/red]",
                )
        except Exception:
            table.add_row(
                f"⏳ {first_project} VMs",
                "[yellow]Not deployed[/yellow]",
                f"Run: superdeploy up -p {first_project}",
            )

    # Print table
    console.print("\n")
    console.print(table)

    # Summary
    console.print("\n[bold cyan]━━━ Summary ━━━[/bold cyan]")
    console.print("[green]✅ Diagnostics complete! Review results above.[/green]")
