"""SuperDeploy CLI - Config command"""
import click
from rich.console import Console

console = Console()

@click.group(name='config')
def config_group():
    """Manage configuration"""
    pass

@config_group.command(name='set')
@click.argument('key_value')
def config_set(key_value):
    """Set config var"""
    key, value = key_value.split('=', 1)
    console.print(f"[green]✅ Set {key}[/green]")

@config_group.command(name='get')
@click.argument('key')
def config_get(key):
    """Get config var"""
    console.print(f"[cyan]{key}=value[/cyan]")

@config_group.command(name='list')
def config_list():
    """List all config vars"""
    console.print("[cyan]Listing config...[/cyan]")
