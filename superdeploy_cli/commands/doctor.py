"""SuperDeploy CLI - Doctor command"""

import click
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from superdeploy_cli.utils import load_env, find_env_file

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
            check_cmd.split(),
            check=True,
            capture_output=True,
            text=True
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
    console.print(
        Panel.fit(
            "[bold cyan]🏥 SuperDeploy System Diagnostics[/bold cyan]\n\n"
            "[white]Running comprehensive health check...[/white]",
            border_style="cyan",
        )
    )
    
    # Create table
    table = Table(title="System Health Report")
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Details", style="dim")
    
    # 1. Check required tools
    console.print("\n[cyan]━━━ Checking Tools ━━━[/cyan]")
    
    required_tools = ["python3", "terraform", "ansible", "gcloud", "jq", "gh", "age", "ssh"]
    
    for tool in required_tools:
        if check_tool(tool):
            table.add_row(f"✅ {tool}", "[green]Installed[/green]", "")
        else:
            table.add_row(
                f"❌ {tool}",
                "[red]Missing[/red]",
                f"brew install {tool}"
            )
    
    # 2. Check authentication
    console.print("[cyan]━━━ Checking Authentication ━━━[/cyan]")
    
    # GCloud
    gcloud_ok, gcloud_project = check_auth("gcloud", "gcloud config get-value project")
    if gcloud_ok and gcloud_project:
        table.add_row("✅ GCloud auth", "[green]OK[/green]", f"Project: {gcloud_project}")
    else:
        table.add_row("❌ GCloud auth", "[red]Not authenticated[/red]", "Run: gcloud auth login")
    
    # GitHub CLI
    gh_ok, gh_user = check_auth("gh", "gh auth status")
    if gh_ok:
        table.add_row("✅ GitHub CLI", "[green]Authenticated[/green]", "")
    else:
        table.add_row("❌ GitHub CLI", "[red]Not authenticated[/red]", "Run: gh auth login")
    
    # 3. Check configuration
    console.print("[cyan]━━━ Checking Configuration ━━━[/cyan]")
    
    env_file = find_env_file()
    if env_file:
        table.add_row("✅ .env file", "[green]Found[/green]", str(env_file))
        
        # Load and validate
        env = load_env()
        
        critical_vars = ["GCP_PROJECT_ID", "SSH_KEY_PATH", "DOCKER_USERNAME", "GITHUB_TOKEN"]
        
        for var in critical_vars:
            value = env.get(var)
            if value and value not in ["", "your-project-id", "your-dockerhub-username", "your-github-token"]:
                table.add_row(f"  ✅ {var}", "[green]Set[/green]", "")
            else:
                table.add_row(f"  ❌ {var}", "[red]Not configured[/red]", "Run: superdeploy init")
    else:
        table.add_row("❌ .env file", "[red]Not found[/red]", "Run: superdeploy init")
    
    # 4. Check VMs (if deployed)
    console.print("[cyan]━━━ Checking Infrastructure ━━━[/cyan]")
    
    if env_file:
        env = load_env()
        
        if env.get("CORE_EXTERNAL_IP"):
            # Try to ping VM
            try:
                subprocess.run(
                    ["ping", "-c", "1", "-W", "2", env["CORE_EXTERNAL_IP"]],
                    check=True,
                    capture_output=True
                )
                table.add_row("✅ Core VM", "[green]Reachable[/green]", env["CORE_EXTERNAL_IP"])
            except subprocess.CalledProcessError:
                table.add_row("❌ Core VM", "[red]Unreachable[/red]", env["CORE_EXTERNAL_IP"])
        else:
            table.add_row("⏳ VMs", "[yellow]Not deployed[/yellow]", "Run: superdeploy up")
    
    # Print table
    console.print("\n")
    console.print(table)
    
    # Summary
    console.print("\n[bold cyan]━━━ Summary ━━━[/bold cyan]")
    console.print("[green]✅ Diagnostics complete! Review results above.[/green]")
