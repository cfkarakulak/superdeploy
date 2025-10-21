"""SuperDeploy CLI - Config command"""

import click
import subprocess
from rich.console import Console
from rich.table import Table
from cli.utils import load_env

console = Console()


@click.group(name="config")
def config_group():
    """Manage configuration variables"""
    pass


@config_group.command(name="set")
@click.argument("key_value")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def config_set(key_value, app, environment):
    """
    Set configuration variable in GitHub Environment

    \b
    Examples:
      superdeploy config:set API_DEBUG=false -a api
      superdeploy config:set SENTRY_DSN=https://... -a api
    """
    env_vars = load_env()

    # Parse key=value
    try:
        key, value = key_value.split("=", 1)
    except ValueError:
        console.print("[red]❌ Invalid format! Use: KEY=VALUE[/red]")
        raise SystemExit(1)

    # Map app to GitHub repo
    repos = {
        "api": env_vars.get("GITHUB_REPO_API", "cheapaio/api"),
        "dashboard": env_vars.get("GITHUB_REPO_DASHBOARD", "cheapaio/dashboard"),
        "services": env_vars.get("GITHUB_REPO_SERVICES", "cheapaio/services"),
    }

    repo = repos.get(app)
    if not repo:
        console.print(f"[red]❌ Unknown app: {app}[/red]")
        raise SystemExit(1)

    console.print(
        f"[cyan]Setting [bold]{key}[/bold] for [bold]{app}[/bold] ({environment})...[/cyan]"
    )

    try:
        # Use gh CLI to set secret
        subprocess.run(
            ["gh", "secret", "set", key, "-b", value, "-e", environment, "-R", repo],
            check=True,
            capture_output=True,
        )

        console.print(f"[green]✅ {key} set successfully![/green]")
        console.print("[dim]Note: Redeploy for changes to take effect[/dim]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to set secret: {e.stderr.decode()}[/red]")
        raise SystemExit(1)


@config_group.command(name="get")
@click.argument("key")
@click.option("-a", "--app", required=True, help="App name")
def config_get(key, app):
    """
    Get configuration variable (from local .env)

    \b
    Examples:
      superdeploy config:get POSTGRES_PASSWORD -a api
    """
    env_vars = load_env()

    value = env_vars.get(key)

    if value:
        console.print(f"[cyan]{key}[/cyan]=[green]{value}[/green]")
    else:
        console.print(f"[yellow]⚠️  {key} not found in .env[/yellow]")
        raise SystemExit(1)


@config_group.command(name="list")
@click.option("-a", "--app", help="Filter by app")
def config_list(app):
    """
    List all configuration variables

    \b
    Examples:
      superdeploy config:list           # All vars
      superdeploy config:list -a api    # App-specific
    """
    env_vars = load_env()

    # Create table
    table = Table(title="Configuration Variables")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    # App-specific filtering
    if app:
        # Show only app-related vars
        prefixes = ["POSTGRES_", "RABBITMQ_", "REDIS_", "API_", "SENTRY_"]
        filtered = {
            k: v for k, v in env_vars.items() if any(k.startswith(p) for p in prefixes)
        }
    else:
        filtered = env_vars

    # Add rows
    for key, value in sorted(filtered.items()):
        # Mask sensitive values
        if any(
            sensitive in key.upper()
            for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY"]
        ):
            masked_value = "***" + value[-4:] if len(value) > 4 else "***"
            table.add_row(key, masked_value)
        else:
            table.add_row(key, value[:50] + "..." if len(value) > 50 else value)

    console.print(table)


@config_group.command(name="unset")
@click.argument("key")
@click.option("-a", "--app", required=True, help="App name")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def config_unset(key, app, environment):
    """
    Unset (delete) configuration variable

    \b
    Examples:
      superdeploy config:unset SENTRY_DSN -a api
    """
    # Map app to GitHub repo
    env_vars = load_env()

    repos = {
        "api": env_vars.get("GITHUB_REPO_API", "cheapaio/api"),
        "dashboard": env_vars.get("GITHUB_REPO_DASHBOARD", "cheapaio/dashboard"),
        "services": env_vars.get("GITHUB_REPO_SERVICES", "cheapaio/services"),
    }

    repo = repos.get(app)
    if not repo:
        console.print(f"[red]❌ Unknown app: {app}[/red]")
        raise SystemExit(1)

    console.print(
        f"[yellow]Removing [bold]{key}[/bold] from [bold]{app}[/bold] ({environment})...[/yellow]"
    )

    try:
        # Use gh CLI to delete secret
        subprocess.run(
            ["gh", "secret", "delete", key, "-e", environment, "-R", repo],
            check=True,
            capture_output=True,
        )

        console.print(f"[green]✅ {key} removed successfully![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to delete secret: {e.stderr.decode()}[/red]")
        raise SystemExit(1)
