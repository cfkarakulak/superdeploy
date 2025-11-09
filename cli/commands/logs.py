"""SuperDeploy CLI - Logs command (Heroku-style beautiful logs)"""

import click
import re
from datetime import datetime
from cli.base import ProjectCommand


class LogsCommand(ProjectCommand):
    """View application logs with beautiful formatting."""

    # Color schemes for different log levels
    LOG_COLORS = {
        'ERROR': 'red',
        'CRITICAL': 'bold red',
        'WARNING': 'yellow',
        'INFO': 'blue',
        'DEBUG': 'cyan',
        'SUCCESS': 'green',
    }

    def __init__(
        self,
        project_name: str,
        app_name: str,
        follow: bool = False,
        lines: int = 100,
        verbose: bool = False,
        filter_level: str = None,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.follow = follow
        self.lines = lines
        self.filter_level = filter_level

    def parse_log_line(self, line: str) -> dict:
        """Parse log line and extract components."""
        # Try to detect log level
        level = None
        for lvl in ['ERROR', 'CRITICAL', 'WARNING', 'INFO', 'DEBUG']:
            if lvl in line.upper():
                level = lvl
                break
        
        # Try to extract timestamp (common formats)
        timestamp = None
        # ISO format: 2024-11-09T12:34:56
        iso_match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', line)
        if iso_match:
            timestamp = iso_match.group(0)
        
        return {
            'level': level,
            'timestamp': timestamp,
            'message': line.strip(),
        }

    def colorize_log(self, parsed: dict) -> str:
        """Format log line simply - original logs already have colors."""
        timestamp = parsed['timestamp']
        message = parsed['message']
        
        # Just add our timestamp if one doesn't exist
        if timestamp:
            return message  # Log already has timestamp
        else:
            now = datetime.now().strftime('%H:%M:%S')
            return f"\033[2m{now}\033[0m {message}"

    def execute(self) -> None:
        """Execute logs command."""
        # Show minimal header for logs (Heroku-style)
        self.console.print()
        self.console.print(f"[bold cyan]📋 {self.project_name}/{self.app_name}[/bold cyan]", end="")
        self.console.print(f" [dim]({self.lines} lines" + (" | following" if self.follow else "") + ")[/dim]")
        self.console.print()

        # Require deployment
        self.require_deployment()

        # Get VM and IP
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)
        except Exception as e:
            self.handle_error(e)
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Container name (use underscore, not dash)
        container_name = f"{self.project_name}_{self.app_name}"

        try:
            # Stream logs
            if self.follow:
                self.console.print("[dim]→ Press Ctrl+C to stop[/dim]\n")

            process = ssh_service.docker_logs(
                vm_ip, container_name, follow=self.follow, tail=self.lines
            )

            # Stream and colorize output
            if process.stdout:
                for line in process.stdout:
                    if not line.strip():
                        continue
                    
                    # Parse and colorize
                    parsed = self.parse_log_line(line)
                    
                    # Filter by level if specified
                    if self.filter_level and parsed['level'] != self.filter_level.upper():
                        continue
                    
                    colored_line = self.colorize_log(parsed)
                    # Use print instead of console.print to avoid double-rendering
                    print(colored_line)

            process.wait()

            if not self.follow:
                self.console.print(f"\n[dim]✓ Log streaming complete[/dim]")

        except KeyboardInterrupt:
            self.console.print(f"\n[dim]✓ Stopped by user[/dim]")
            if process:
                process.terminate()
        except Exception as e:
            self.handle_error(e, "Failed to fetch logs")
            raise SystemExit(1)


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, storefront, services)")
@click.option("-f", "--follow", is_flag=True, help="Follow logs in real-time (like tail -f)")
@click.option("-n", "--lines", default=100, help="Number of recent lines to show")
@click.option("--level", help="Filter by log level (ERROR, WARNING, INFO, DEBUG)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def logs(project, app, follow, lines, level, verbose):
    """
    View application logs with beautiful formatting (Heroku-style)
    
    Features:
    - Color-coded log levels (ERROR=red, WARNING=yellow, INFO=blue, etc.)
    - Automatic timestamp detection and formatting
    - HTTP request highlighting
    - Real-time streaming with -f flag
    - Filter by log level with --level flag

    Examples:
        superdeploy cheapa:logs -a api              # Last 100 lines
        superdeploy cheapa:logs -a api -f           # Follow logs in real-time
        superdeploy cheapa:logs -a api -n 500       # Last 500 lines
        superdeploy cheapa:logs -a api --level ERROR # Only show errors
        superdeploy cheapa:logs -a storefront -f    # Follow storefront logs
    """
    cmd = LogsCommand(
        project, 
        app, 
        follow=follow, 
        lines=lines, 
        verbose=verbose,
        filter_level=level
    )
    cmd.run()
