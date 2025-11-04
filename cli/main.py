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
    down,
    promote,
    metrics,
    update_firewall,
    subnets,
    tunnel,
)
from cli.commands.domain import domain_add, domain_list, domain_remove
from cli.commands.config import config_set, config_get, config_list, config_unset
from cli.commands.env import env_list, env_check
from cli.commands.releases import releases_list
from cli.commands.switch import releases_rollback
from cli.commands.backup import backups_create
from cli.commands.monitoring import monitoring_sync, monitoring_status
from cli.commands.orchestrator import (
    orchestrator_init,
    orchestrator_up,
    orchestrator_down,
    orchestrator_status,
)
from cli.commands.project import projects_deploy
from cli.commands.validate import validate_project, validate_addons

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
# Register up command (with improved logging)
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
# Register config commands (Heroku-style with colons)
cli.add_command(config_set)
cli.add_command(config_get)
cli.add_command(config_list)
cli.add_command(config_unset)
# Register env commands (Heroku-style with colons)
cli.add_command(env_list)
cli.add_command(env_check)
# Register releases commands (Heroku-style with colons)
cli.add_command(releases_list)
cli.add_command(releases_rollback)
# Register project commands (Heroku-style with colons)
cli.add_command(projects_deploy)
cli.add_command(promote.promote)
# Register domain commands (Heroku-style with colons)
cli.add_command(domain_add)
cli.add_command(domain_list)
cli.add_command(domain_remove)
# Register backup commands (Heroku-style with colons)
cli.add_command(backups_create)
# Register validate commands (Heroku-style with colons)
cli.add_command(validate_project)
cli.add_command(validate_addons)
cli.add_command(metrics.metrics)
# Register orchestrator commands (Heroku-style with colons)
cli.add_command(orchestrator_init)
cli.add_command(orchestrator_up)
cli.add_command(orchestrator_down)
cli.add_command(orchestrator_status)
cli.add_command(update_firewall.update_firewall, name="update-firewall")
# Register monitoring commands (Heroku-style with colons)
cli.add_command(monitoring_sync)
cli.add_command(monitoring_status)
cli.add_command(subnets.subnets)
cli.add_command(tunnel.tunnel)


if __name__ == "__main__":
    cli()
