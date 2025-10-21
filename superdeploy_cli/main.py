#!/usr/bin/env python3
"""SuperDeploy CLI - Main entry point"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from superdeploy_cli.commands import init, up, sync, status, logs, run_cmd, deploy
from superdeploy_cli.commands import scale, restart, doctor, config

console = Console()

BANNER = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]  [bold white]SuperDeploy[/bold white] - Heroku-like PaaS (Self-Hosted)         [bold cyan]║[/bold cyan]
[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]
"""


@click.group()
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx):
    """
    SuperDeploy - Deploy production apps like Heroku, on your own infrastructure.
    
    \b
    Quick Start:
      superdeploy init      # Interactive setup
      superdeploy up        # Deploy infrastructure
      superdeploy sync      # Sync secrets to GitHub
      superdeploy deploy    # Deploy apps
    
    \b
    Daily Workflow:
      git push origin production  # Auto-deploy!
      superdeploy logs -a api -f  # Watch logs
      superdeploy run api "cmd"   # Run commands
      superdeploy scale api=3     # Scale services
    """
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print("[yellow]Run 'superdeploy --help' for usage[/yellow]\n")


# Register commands
cli.add_command(init.init)
cli.add_command(up.up)
cli.add_command(sync.sync)
cli.add_command(status.status)
cli.add_command(logs.logs)
cli.add_command(run_cmd.run)
cli.add_command(deploy.deploy)
cli.add_command(scale.scale)
cli.add_command(restart.restart)
cli.add_command(doctor.doctor)
cli.add_command(config.config_group)


if __name__ == "__main__":
    cli()

