"""SuperDeploy CLI - Restart command"""

import click
from rich.console import Console
from superdeploy_cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
@click.argument("app")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def restart(app, environment):
    """
    Restart service
    
    \b
    Examples:
      superdeploy restart api        # Restart API service
      superdeploy restart dashboard  # Restart Dashboard
    """
    env_vars = load_env()
    
    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env_vars, required):
        raise SystemExit(1)
    
    console.print(f"[cyan]🔄 Restarting [bold]{app}[/bold]...[/cyan]")
    
    # SSH command
    ssh_host = env_vars["CORE_EXTERNAL_IP"]
    ssh_user = env_vars.get("SSH_USER", "superdeploy")
    ssh_key = env_vars["SSH_KEY_PATH"].replace("~", env_vars.get("HOME", "/root"))
    
    restart_cmd = f"cd /opt/superdeploy/compose && docker-compose restart {app}"
    
    try:
        result = ssh_command(
            host=ssh_host,
            user=ssh_user,
            key_path=ssh_key,
            cmd=restart_cmd
        )
        
        console.print(f"[green]✅ {app} restarted successfully![/green]")
        
        # Show status
        status_cmd = f"docker ps --filter name=superdeploy-{app}-1 --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'"
        status = ssh_command(host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=status_cmd)
        
        console.print(f"\n[cyan]Status:[/cyan]")
        console.print(status)
        
    except Exception as e:
        console.print(f"[red]❌ Restart failed: {e}[/red]")
        raise SystemExit(1)
