#!/usr/bin/env python3
"""SuperDeploy CLI - Main entry point"""

import click
from rich.console import Console
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.commands import (
    init,
    generate,
    up,
    sync,
    sync_infra,
    sync_repos,
    status,
    logs,
    run_cmd,
    deploy,
    scale,
    restart,
    doctor,
    config,
    env,
    releases,
    down,
    project,
    promote,
    backup,
    validate,
    metrics,
)

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
cli.add_command(generate.generate)
cli.add_command(up.up)
cli.add_command(down.down)
cli.add_command(sync.sync)
cli.add_command(sync_infra.sync_infra, name="sync:infra")
cli.add_command(sync_repos.sync_repos, name="sync:repos")
cli.add_command(status.status)
cli.add_command(logs.logs)
cli.add_command(run_cmd.run)
cli.add_command(deploy.deploy)
cli.add_command(scale.scale)
cli.add_command(restart.restart)
cli.add_command(doctor.doctor)
cli.add_command(config.config_group)
cli.add_command(env.env_group)
cli.add_command(releases.releases)
cli.add_command(releases.rollback)
cli.add_command(project.project)
cli.add_command(promote.promote)
cli.add_command(backup.backup)
cli.add_command(validate.validate)
cli.add_command(metrics.metrics)


if __name__ == "__main__":
    cli()
