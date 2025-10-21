"""SuperDeploy CLI - Status command"""

import click
from rich.console import Console
from rich.table import Table
from superdeploy_cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
def status():
    """
    Show infrastructure status
    
    Displays:
    - VMs status
    - Forgejo status
    - Runner status
    - Container status
    """
    env = load_env()
    
    # Validate
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env, required):
        console.print("[yellow]⚠️  Limited status (IPs not configured yet)[/yellow]")
        
        # Show basic info
        table = Table(title="Infrastructure Status (Partial)")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="yellow")
        
        table.add_row("Configuration", "✅ .env loaded")
        table.add_row("VMs", "⏳ Not deployed yet")
        
        console.print(table)
        return
    
    console.print("[cyan]📊 Fetching status...[/cyan]\n")
    
    # Create table
    table = Table(title="SuperDeploy Infrastructure Status")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    # Check VMs
    ssh_host = env["CORE_EXTERNAL_IP"]
    ssh_user = env.get("SSH_USER", "superdeploy")
    ssh_key = env["SSH_KEY_PATH"].replace("~", env.get("HOME", "/root"))
    
    try:
        # Check core VM
        uptime = ssh_command(host=ssh_host, user=ssh_user, key_path=ssh_key, cmd="uptime -p")
        table.add_row("Core VM", "✅ Running", f"{ssh_host} ({uptime})")
    except:
        table.add_row("Core VM", "❌ Unreachable", ssh_host)
    
    try:
        # Check Forgejo
        forgejo_check = ssh_command(
            host=ssh_host,
            user=ssh_user,
            key_path=ssh_key,
            cmd="curl -s http://localhost:3001/api/v1/version | jq -r '.version' || echo 'down'"
        )
        
        if "down" not in forgejo_check:
            table.add_row("Forgejo", "✅ Active", f"v{forgejo_check.strip()}")
        else:
            table.add_row("Forgejo", "❌ Down", "Not responding")
    except:
        table.add_row("Forgejo", "❌ Error", "Cannot check")
    
    try:
        # Check Runner
        runner_status = ssh_command(
            host=ssh_host,
            user=ssh_user,
            key_path=ssh_key,
            cmd="systemctl is-active forgejo-runner || echo 'inactive'"
        )
        
        if "active" in runner_status:
            table.add_row("Runner", "✅ Active", "core-runner")
        else:
            table.add_row("Runner", "❌ Inactive", runner_status.strip())
    except:
        table.add_row("Runner", "❌ Error", "Cannot check")
    
    try:
        # Check containers
        containers = ssh_command(
            host=ssh_host,
            user=ssh_user,
            key_path=ssh_key,
            cmd="docker ps --filter name=superdeploy --format '{{.Names}}: {{.Status}}' | head -5"
        )
        
        for line in containers.strip().split("\n"):
            if line:
                name, status = line.split(":", 1)
                name = name.replace("superdeploy-", "").replace("-1", "")
                
                if "Up" in status:
                    table.add_row(f"  {name}", "✅ Running", status.strip())
                else:
                    table.add_row(f"  {name}", "❌ Down", status.strip())
    except:
        table.add_row("Containers", "❌ Error", "Cannot check")
    
    console.print(table)
    
    # Show URLs
    console.print(f"\n[cyan]🌐 Access URLs:[/cyan]")
    console.print(f"  Forgejo:    http://{ssh_host}:3001")
    console.print(f"  API:        http://{ssh_host}:8000")
    console.print(f"  Dashboard:  http://{ssh_host}")
