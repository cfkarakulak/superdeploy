"""SuperDeploy CLI - Logs command (Heroku-style beautiful logs)"""

import click
import re
from datetime import datetime
from cli.base import ProjectCommand


class LogsCommand(ProjectCommand):
    """View application logs with beautiful formatting."""

    # Color schemes for different log levels
    LOG_COLORS = {
        "ERROR": "red",
        "CRITICAL": "bold red",
        "WARNING": "yellow",
        "INFO": "blue",
        "DEBUG": "cyan",
        "SUCCESS": "green",
    }

    def __init__(
        self,
        project_name: str,
        app_name: str,
        lines: int = 100,
        verbose: bool = False,
        filter_level: str = None,
        grep_pattern: str = None,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.follow = True  # Always follow by default
        self.lines = lines
        self.filter_level = filter_level
        self.grep_pattern = grep_pattern
        self.line_count = 0

    def parse_log_line(self, line: str) -> dict:
        """Parse log line and extract components."""
        # Try to detect log level
        level = None
        for lvl in ["ERROR", "CRITICAL", "WARNING", "INFO", "DEBUG"]:
            if lvl in line.upper():
                level = lvl
                break

        # Try to extract timestamp (common formats)
        timestamp = None
        # ISO format: 2024-11-09T12:34:56
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", line)
        if iso_match:
            timestamp = iso_match.group(0)

        return {
            "level": level,
            "timestamp": timestamp,
            "message": line.strip(),
        }

    def colorize_log(self, parsed: dict) -> str:
        """Format log line simply - original logs already have colors."""
        timestamp = parsed["timestamp"]
        message = parsed["message"]

        # Just add our timestamp if one doesn't exist
        if timestamp:
            return message  # Log already has timestamp
        else:
            now = datetime.now().strftime("%H:%M:%S")
            return f"\033[2m{now}\033[0m {message}"

    def matches_filters(self, parsed: dict, line: str) -> bool:
        """Check if line matches all filters."""
        # Filter by level if specified
        if self.filter_level and parsed["level"] != self.filter_level.upper():
            return False

        # Filter by grep pattern if specified
        if self.grep_pattern:
            try:
                if not re.search(self.grep_pattern, line, re.IGNORECASE):
                    return False
            except re.error:
                # Invalid regex, treat as literal string
                if self.grep_pattern.lower() not in line.lower():
                    return False

        return True

    def execute(self) -> None:
        """Execute logs command."""
        # Show minimal header for logs (Heroku-style)
        filters = []
        if self.filter_level:
            filters.append(f"level={self.filter_level}")
        if self.grep_pattern:
            filters.append(f"grep='{self.grep_pattern}'")

        filter_str = f" | {', '.join(filters)}" if filters else ""

        self.console.print()
        self.console.print(
            f"[bold cyan]📋 {self.project_name}/{self.app_name}[/bold cyan]", end=""
        )
        self.console.print(f" [dim](streaming{filter_str})[/dim]")
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
            # Show helpful message
            self.console.print("[dim]→ Streaming logs... Press Ctrl+C to stop[/dim]\n")

            process = ssh_service.docker_logs(
                vm_ip, container_name, follow=self.follow, tail=self.lines
            )

            # Stream and filter output
            if process.stdout:
                for line in process.stdout:
                    if not line.strip():
                        continue

                    # Parse log line
                    parsed = self.parse_log_line(line)

                    # Apply filters
                    if not self.matches_filters(parsed, line):
                        continue

                    # Colorize and print
                    colored_line = self.colorize_log(parsed)
                    print(colored_line)
                    self.line_count += 1

            process.wait()

        except KeyboardInterrupt:
            self.console.print(
                f"\n[dim]✓ Stopped (displayed {self.line_count} lines)[/dim]"
            )
            if process:
                process.terminate()
        except Exception as e:
            self.handle_error(e, "Failed to fetch logs")
            raise SystemExit(1)


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, storefront, services)")
@click.option(
    "-n", "--lines", default=100, help="Number of recent lines to show before streaming"
)
@click.option("--level", help="Filter by log level (ERROR, WARNING, INFO, DEBUG)")
@click.option("--grep", "grep_pattern", help="Filter logs by pattern (supports regex)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def logs(project, app, lines, level, grep_pattern, verbose):
    """
    Stream application logs in real-time (always tails)

    Features:
    - Always streams logs in real-time (like Heroku logs)
    - Filter by log level with --level flag
    - Search logs with --grep flag (supports regex)
    - Clean, colorful output
    - Press Ctrl+C to stop

    Examples:
        # Stream logs (starts from last 100 lines)
        superdeploy cheapa:logs -a api

        # Stream from last 500 lines
        superdeploy cheapa:logs -a api -n 500

        # Only show errors while streaming
        superdeploy cheapa:logs -a api --level ERROR

        # Search for specific pattern
        superdeploy cheapa:logs -a api --grep "database"

        # Combine filters (grep + level)
        superdeploy cheapa:logs -a api --grep "GET.*200" --level INFO

        # Monitor errors in real-time
        superdeploy cheapa:logs -a storefront --level ERROR
    """
    cmd = LogsCommand(
        project,
        app,
        lines=lines,
        verbose=verbose,
        filter_level=level,
        grep_pattern=grep_pattern,
    )
    cmd.run()
