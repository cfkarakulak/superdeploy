#!/usr/bin/env python3
"""SuperDeploy CLI - Main entry point"""

# ⚠️ CRITICAL: Set environment BEFORE any imports!
# This ensures rich/rich-click detect colors correctly
import os
import sys

# FORCE COLORS: Remove NO_COLOR (set by Cursor/IDEs)
if "NO_COLOR" in os.environ:
    del os.environ["NO_COLOR"]

# Set color-forcing environment variables
os.environ["FORCE_COLOR"] = "1"
os.environ["TERM"] = "xterm-256color"
os.environ["COLORTERM"] = "truecolor"

# NOW import everything else
from pathlib import Path
from rich.console import Console

# Rich-Click: Beautiful CLI help with colors!
import rich_click as click

# Configure rich-click for beautiful output 🎨
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.MAX_WIDTH = 100
click.rich_click.COLOR_SYSTEM = "truecolor"
click.rich_click.FORCE_TERMINAL = True

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
    subnets,
    tunnel,
    dashboard,
)
from cli.commands.ps import ps

# NOTE: up, down, plan are imported dynamically in NamespacedGroup (not registered as standalone commands)
from cli.commands.domains import domains_add, domains_list, domains_remove
from cli.commands.config import (
    config_set,
    config_get,
    config_list,
    config_unset,
    config_show,
)
from cli.commands.env import env_list, env_check
from cli.commands.releases import releases_list
from cli.commands.switch import releases_switch
from cli.commands.backup import backups_create
from cli.commands.orchestrator import (
    orchestrator_init,
    orchestrator_up,
    orchestrator_down,
    orchestrator_status,
)
from cli.commands.project import projects_deploy
from cli.commands.validate import validate_addons
from cli.commands.addons import (
    addons,
    addons_list,
    addons_info,
    addons_add,
    addons_remove,
    addons_attach,
    addons_detach,
)

console = Console()

BANNER = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]  [bold white]SuperDeploy[/bold white] - Heroku-like PaaS (Self-Hosted)         [bold cyan]║[/bold cyan]
[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]
"""


def handle_cli_errors(func):
    """Decorator to handle CLI errors gracefully."""
    import functools
    from click.exceptions import ClickException, UsageError, MissingParameter

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MissingParameter as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e.format_message()}\n")
            if e.ctx and e.ctx.command:
                console.print(
                    f"[dim]Run[/dim] [cyan]superdeploy {e.ctx.command.name} --help[/cyan] [dim]for usage information[/dim]\n"
                )
            sys.exit(1)
        except UsageError as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e.format_message()}\n")
            if e.ctx and e.ctx.command:
                console.print(
                    f"[dim]Run[/dim] [cyan]superdeploy {e.ctx.command.name} --help[/cyan] [dim]for usage information[/dim]\n"
                )
            sys.exit(1)
        except TypeError as e:
            error_msg = str(e)
            if "missing" in error_msg and "required positional argument" in error_msg:
                # Extract parameter name from error message
                import re

                match = re.search(r"'(\w+)'", error_msg)
                param_name = match.group(1) if match else "parameter"

                console.print(
                    f"\n[bold red]✗ Error:[/bold red] Missing required argument: [yellow]{param_name}[/yellow]\n"
                )

                # Try to provide helpful context
                if param_name == "project":
                    console.print("[dim]This command requires a project name.[/dim]")
                    console.print("\n[bold]Examples:[/bold]")
                    console.print(
                        "  [cyan]superdeploy myproject:init[/cyan]    [dim]# Initialize project[/dim]"
                    )
                    console.print(
                        "  [cyan]superdeploy myproject:up[/cyan]      [dim]# Deploy project[/dim]"
                    )
                    console.print(
                        "  [cyan]superdeploy myproject:status[/cyan]  [dim]# Check status[/dim]\n"
                    )
                else:
                    console.print(
                        "[dim]Run[/dim] [cyan]superdeploy --help[/cyan] [dim]for available commands[/dim]\n"
                    )
            else:
                # Re-raise if it's not a parameter error
                raise
            sys.exit(1)
        except ClickException as e:
            # Click's built-in exceptions (already formatted)
            e.show()
            sys.exit(e.exit_code)
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⚠️  Operation cancelled by user[/yellow]")
            sys.exit(130)
        except Exception as e:
            # Unexpected errors
            console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}\n")
            console.print("[dim]If this persists, please report this issue.[/dim]\n")

            # Show traceback in verbose mode or if DEBUG env var is set
            if os.environ.get("DEBUG") or os.environ.get("VERBOSE"):
                import traceback

                console.print("[dim]Traceback:[/dim]")
                traceback.print_exc()
            sys.exit(1)

    return wrapper


class NamespacedGroup(click.RichGroup):
    """Custom Click group that supports namespaced commands like 'project:up'"""

    def invoke(self, ctx):
        """Override invoke to add error handling."""
        try:
            return super().invoke(ctx)
        except Exception:
            # Let the error handler deal with it
            raise

    def get_command(self, ctx, cmd_name):
        # Check if command has namespace (e.g., "cheapa:up", "orchestrator:down")
        if ":" in cmd_name:
            # First check if this is a registered command (e.g., orchestrator:up already exists)
            existing_cmd = super().get_command(ctx, cmd_name)
            if existing_cmd:
                return existing_cmd

            # Dynamic namespace resolution for project commands
            namespace, sub_cmd = cmd_name.split(":", 1)

            # Check if sub_cmd has another colon (e.g., "config:set", "domains:add")
            # This handles: cheapa:config:set, cheapa:domains:add
            if ":" in sub_cmd:
                # Second-level namespace (e.g., config:set, domains:add)
                # These are already registered commands, just inject project
                base_command = super().get_command(ctx, sub_cmd)
                if base_command:
                    import functools

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
                "ps",
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
                    "ps": ps,
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
      superdeploy orchestrator:up   # Deploy monitoring (once)
      superdeploy myapp:init        # Create project
      superdeploy myapp:up          # Deploy project
      superdeploy myapp:sync        # Sync secrets

    \b
    Daily Workflow:
      git push origin production  # Auto-deploy!
      superdeploy logs -a api -f  # Watch logs
      superdeploy run api "cmd"   # Run commands
      superdeploy ps              # View app processes
      superdeploy scale api=3     # Scale replicas

    \b
    Namespaced Commands (project-specific operations):
      superdeploy <project>:up              # Deploy infrastructure
      superdeploy <project>:down            # Destroy infrastructure
      superdeploy <project>:plan            # Show deployment changes
      superdeploy <project>:config:set KEY=VAL # Set config variable
      superdeploy <project>:domains:add app.com # Add domain
      superdeploy <project>:sync            # Sync secrets to GitHub
      superdeploy <project>:ps              # View app processes & replicas
      superdeploy <project>:scale web=3     # Scale app replicas
      superdeploy <project>:addons          # List addons
      superdeploy <project>:addons:add postgres --name primary # Add addon
      superdeploy <project>:addons:attach databases.primary --app api # Attach addon
      superdeploy orchestrator:up           # Deploy orchestrator
      superdeploy orchestrator:domains:add g.com # Add orchestrator domain
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
cli.add_command(releases_switch)
# Register project commands (Heroku-style with colons)
cli.add_command(projects_deploy)
cli.add_command(promote.promote)
# Register domains commands (Heroku-style with colons)
cli.add_command(domains_add)
cli.add_command(domains_list)
cli.add_command(domains_remove)
# Register addons commands (Heroku-style with colons)
cli.add_command(addons)
cli.add_command(addons_list)
cli.add_command(addons_info)
cli.add_command(addons_add)
cli.add_command(addons_remove)
cli.add_command(addons_attach)
cli.add_command(addons_detach)
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
cli.add_command(subnets.subnets)
cli.add_command(tunnel.tunnel)
# Register dashboard commands
cli.add_command(dashboard.dashboard)


@handle_cli_errors
def main():
    """Main entry point with error handling."""
    cli()


if __name__ == "__main__":
    main()
