#!/usr/bin/env python3
"""SuperDeploy CLI - Main entry point"""

from rich.console import Console
from pathlib import Path
import sys

# Rich-Click: Beautiful CLI help with colors!
import rich_click as click

# Configure rich-click for beautiful output 🎨
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.COLOR_SYSTEM = "auto"

# COMMANDS: Bold cyan (beautiful!)
click.rich_click.STYLE_COMMAND = "bold cyan"

# OPTIONS: Bold magenta (stands out!)
click.rich_click.STYLE_OPTION = "bold magenta"
click.rich_click.STYLE_SWITCH = "bold green"
click.rich_click.STYLE_ARGUMENT = "bold yellow"

# HEADERS: Bold cyan
click.rich_click.STYLE_HEADER_TEXT = "bold cyan"
click.rich_click.STYLE_USAGE = "bold yellow"
click.rich_click.STYLE_USAGE_COMMAND = "bold cyan"

# HELP TEXT: Clear and readable
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "bold white"
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.STYLE_OPTION_HELP = ""

# METAVARS: Yellow
click.rich_click.STYLE_METAVAR = "bold yellow"
click.rich_click.STYLE_METAVAR_APPEND = "dim yellow"
click.rich_click.STYLE_METAVAR_SEPARATOR = "dim"

# REQUIRED: Red
click.rich_click.STYLE_REQUIRED_SHORT = "bold red"
click.rich_click.STYLE_REQUIRED_LONG = "bold red"

# DEFAULTS: Dim cyan
click.rich_click.STYLE_OPTION_DEFAULT = "dim cyan"
click.rich_click.STYLE_EPILOG_TEXT = "dim"
click.rich_click.STYLE_FOOTER_TEXT = "dim"

# PANEL BORDERS: Cyan
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "cyan"
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "cyan"

# ALIGNMENT
click.rich_click.ALIGN_OPTIONS_PANEL = "left"
click.rich_click.ALIGN_ERRORS_PANEL = "left"
click.rich_click.ERRORS_EPILOGUE = ""

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.commands import (
    init,
    logs,
    run_cmd,
    deploy,
    restart,
    doctor,
    promote,
    update_firewall,
    subnets,
    tunnel,
)

# NOTE: up, down, plan are imported dynamically in NamespacedGroup (not registered as standalone commands)
from cli.commands.domain import domain_add, domain_list, domain_remove
from cli.commands.config import (
    config_set,
    config_get,
    config_list,
    config_unset,
    config_show,
)
from cli.commands.env import env_list, env_check
from cli.commands.releases import releases_list
from cli.commands.switch import releases_rollback
from cli.commands.backup import backups_create
from cli.commands.orchestrator import (
    orchestrator_init,
    orchestrator_up,
    orchestrator_down,
    orchestrator_status,
)
from cli.commands.project import projects_deploy
from cli.commands.validate import validate_addons

console = Console()

BANNER = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]  [bold white]SuperDeploy[/bold white] - Heroku-like PaaS (Self-Hosted)         [bold cyan]║[/bold cyan]
[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]
"""


class NamespacedGroup(click.Group):
    """Custom Click group that supports namespaced commands like 'project:up'"""

    def get_command(self, ctx, cmd_name):
        # Check if command has namespace (e.g., "cheapa:up", "orchestrator:down")
        if ":" in cmd_name:
            # First check if this is a registered command (e.g., orchestrator:up already exists)
            existing_cmd = super().get_command(ctx, cmd_name)
            if existing_cmd:
                return existing_cmd

            # Dynamic namespace resolution for project commands
            namespace, sub_cmd = cmd_name.split(":", 1)

            # Get the base command (up, down, etc.)
            base_command = super().get_command(ctx, sub_cmd)

            # If not registered, try to import directly (for unregistered project commands)
            project_commands = [
                "up",
                "down",
                "plan",
                "generate",
                "status",
                "sync",
                "validate",
                "scale",
                "metrics",
            ]

            if base_command is None and sub_cmd in project_commands:
                from cli.commands import (
                    up,
                    down,
                    plan,
                    generate,
                    status,
                    sync,
                    scale,
                    metrics,
                )
                from cli.commands.validate import validate_project

                command_map = {
                    "up": up.up,
                    "down": down.down,
                    "plan": plan.plan,
                    "generate": generate.generate,
                    "status": status.status,
                    "sync": sync.sync,
                    "validate": validate_project,
                    "scale": scale.scale,
                    "metrics": metrics.metrics,
                }
                base_command = command_map.get(sub_cmd)

            if base_command is None:
                return None

            # Create a wrapper that injects the project parameter
            import functools

            # Clone the command to avoid modifying the original
            wrapper = click.Command(
                name=cmd_name,
                callback=functools.partial(
                    self._inject_project, base_command.callback, namespace
                ),
                params=base_command.params,
                help=base_command.help,
            )

            # Remove the --project/-p option if it exists
            wrapper.params = [p for p in wrapper.params if p.name != "project"]

            return wrapper

        # Regular command without namespace
        return super().get_command(ctx, cmd_name)

    def _inject_project(self, original_callback, project_name, *args, **kwargs):
        """Inject project parameter into the command"""
        # Add project to kwargs if the command expects it
        kwargs["project"] = project_name
        return original_callback(*args, **kwargs)

    def list_commands(self, ctx):
        """List all available commands"""
        return super().list_commands(ctx)


@click.group(cls=NamespacedGroup)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    SuperDeploy - Deploy production apps like Heroku, on your own infrastructure.

    \b
    Quick Start:
      [red]superdeploy orchestrator:up[/red]  # Deploy monitoring (once)
      superdeploy init -p myapp     # Create project
      [red]superdeploy myapp:up[/red]         # Deploy project
      superdeploy myapp:sync        # Sync secrets

    \b
    Daily Workflow:
      git push origin production  # Auto-deploy!
      superdeploy logs -a api -f  # Watch logs
      superdeploy run api "cmd"   # Run commands
      superdeploy scale api=3     # Scale services

    \b
    Namespaced Commands (required for project operations):
      [cyan]superdeploy <project>:up[/cyan]       # Deploy infrastructure
      [cyan]superdeploy <project>:down[/cyan]     # Destroy infrastructure
      [cyan]superdeploy <project>:plan[/cyan]     # Show deployment changes
      [cyan]superdeploy <project>:status[/cyan]   # Show deployment status
      [cyan]superdeploy <project>:generate[/cyan] # Generate workflow files
      [cyan]superdeploy <project>:sync[/cyan]     # Sync secrets to GitHub
      [cyan]superdeploy <project>:validate[/cyan] # Validate configuration
      [cyan]superdeploy <project>:scale[/cyan]    # Scale services
      [cyan]superdeploy <project>:metrics[/cyan]  # View metrics
      [cyan]superdeploy orchestrator:up[/cyan]    # Deploy orchestrator
      [cyan]superdeploy orchestrator:down[/cyan]  # Destroy orchestrator
    """
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print("[yellow]Run 'superdeploy --help' for usage[/yellow]\n")


# Register commands
cli.add_command(init.init)
# NOTE: Project-specific commands use namespaced syntax: <project>:command
# Examples: cheapa:up, cheapa:generate, cheapa:sync, cheapa:validate, cheapa:status, etc.
cli.add_command(logs.logs)
cli.add_command(run_cmd.run)
cli.add_command(deploy.deploy)
cli.add_command(restart.restart)
cli.add_command(doctor.doctor)
# Register config commands (Heroku-style with colons)
cli.add_command(config_set)
cli.add_command(config_get)
cli.add_command(config_list)
cli.add_command(config_unset)
cli.add_command(config_show)
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
# NOTE: validate:project moved to <project>:validate (namespaced)
cli.add_command(validate_addons)
# NOTE: metrics moved to <project>:metrics (namespaced)
# Register orchestrator commands (Heroku-style with colons)
cli.add_command(orchestrator_init)
cli.add_command(orchestrator_up)
cli.add_command(orchestrator_down)
cli.add_command(orchestrator_status)
cli.add_command(update_firewall.update_firewall, name="update-firewall")
cli.add_command(subnets.subnets)
cli.add_command(tunnel.tunnel)


if __name__ == "__main__":
    cli()
