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
    switch,
    down,
    project,
    promote,
    backup,
    validate,
    metrics,
    orchestrator,
    update_firewall,
    monitoring,
    subnets,
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
def cli(ctx: click.Context) -> None:
    """
    SuperDeploy - Deploy production apps like Heroku, on your own infrastructure.

    \b
    Quick Start:
      superdeploy orchestrator up  # Deploy Forgejo (once)
      superdeploy init -p myapp    # Create project
      superdeploy up -p myapp      # Deploy project
      superdeploy sync -p myapp    # Sync secrets

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
cli.add_command(switch.switch)
cli.add_command(project.project)
cli.add_command(promote.promote)
cli.add_command(backup.backup)
cli.add_command(validate.validate)
cli.add_command(metrics.metrics)
cli.add_command(orchestrator.orchestrator)
cli.add_command(update_firewall.update_firewall, name="update-firewall")
cli.add_command(monitoring.monitoring)
cli.add_command(subnets.subnets)


if __name__ == "__main__":
    cli()
