"""
Logs Command

Stream application logs with filtering and colorization (Heroku-style).
"""

import click
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import subprocess

from cli.base import ProjectCommand


@dataclass
class LogsOptions:
    """Options for logs command."""

    app_name: str
    lines: int = 100
    follow: bool = True
    filter_level: Optional[str] = None
    grep_pattern: Optional[str] = None


@dataclass
class ParsedLogLine:
    """Parsed log line components."""

    level: Optional[str]
    timestamp: Optional[str]
    message: str


class LogParser:
    """
    Parses log lines and extracts structured information.

    Responsibilities:
    - Extract log levels
    - Parse timestamps
    - Identify log components
    """

    LOG_LEVELS = ["ERROR", "CRITICAL", "WARNING", "INFO", "DEBUG"]

    @staticmethod
    def parse(line: str) -> ParsedLogLine:
        """
        Parse log line and extract components.

        Args:
            line: Raw log line

        Returns:
            ParsedLogLine with extracted components
        """
        # Detect log level
        level = None
        for lvl in LogParser.LOG_LEVELS:
            if lvl in line.upper():
                level = lvl
                break

        # Extract timestamp (ISO format: 2024-11-09T12:34:56)
        timestamp = None
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", line)
        if iso_match:
            timestamp = iso_match.group(0)

        return ParsedLogLine(
            level=level,
            timestamp=timestamp,
            message=line.strip(),
        )


class LogColorizer:
    """
    Colorizes log lines based on content.

    Responsibilities:
    - Add timestamps if missing
    - Preserve existing colors
    - Format output
    """

    @staticmethod
    def colorize(parsed: ParsedLogLine) -> str:
        """
        Format log line with colors.

        Args:
            parsed: ParsedLogLine object

        Returns:
            Formatted log line string
        """
        # If log already has timestamp, return as-is (preserve colors)
        if parsed.timestamp:
            return parsed.message

        # Add timestamp if missing
        now = datetime.now().strftime("%H:%M:%S")
        return f"\033[2m{now}\033[0m {parsed.message}"


class LogFilter:
    """
    Filters log lines based on criteria.

    Responsibilities:
    - Filter by log level
    - Filter by regex pattern
    - Combine multiple filters
    """

    def __init__(self, level: Optional[str] = None, pattern: Optional[str] = None):
        """
        Initialize log filter.

        Args:
            level: Filter by log level (ERROR, WARNING, etc.)
            pattern: Filter by regex pattern
        """
        self.level = level.upper() if level else None
        self.pattern = pattern

    def matches(self, parsed: ParsedLogLine, line: str) -> bool:
        """
        Check if line matches all filters.

        Args:
            parsed: Parsed log line
            line: Raw log line

        Returns:
            True if line matches filters
        """
        # Filter by level
        if self.level and parsed.level != self.level:
            return False

        # Filter by pattern
        if self.pattern:
            try:
                if not re.search(self.pattern, line, re.IGNORECASE):
                    return False
            except re.error:
                # Invalid regex, treat as literal string
                if self.pattern.lower() not in line.lower():
                    return False

        return True


class LogsCommand(ProjectCommand):
    """
    Stream application logs with beautiful formatting.

    Features:
    - Real-time streaming (Heroku-style)
    - Filter by log level
    - Search with regex patterns
    - Colorful output
    """

    def __init__(
        self,
        project_name: str,
        options: LogsOptions,
        verbose: bool = False,
        json_output: bool = False,
    ):
        """
        Initialize logs command.

        Args:
            project_name: Name of the project
            options: LogsOptions with configuration
            verbose: Whether to show verbose output
            json_output: Whether to output in JSON format
        """
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.options = options
        self.parser = LogParser()
        self.colorizer = LogColorizer()
        self.filter = LogFilter(options.filter_level, options.grep_pattern)
        self.line_count = 0
        self.process: Optional[subprocess.Popen] = None

    def execute(self) -> None:
        """Execute logs command."""
        self._print_header()
        self.require_deployment()

        # Get VM and IP for app
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.options.app_name)
        except Exception as e:
            self.handle_error(e)
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Find the actual container name (Docker Compose uses dash separator and adds -1 suffix)
        # Try multiple formats: project-app-1, project-app, project_app
        container_name = self._find_container(ssh_service, vm_ip)

        if not container_name:
            raise Exception(
                f"Container not found for {self.project_name}/{self.options.app_name}. "
                f"Make sure the app is running."
            )

        try:
            self.console.print("[dim]→ Streaming logs... Press Ctrl+C to stop[/dim]\n")

            # Start streaming logs
            self.process = ssh_service.docker_logs(
                vm_ip,
                container_name,
                follow=self.options.follow,
                tail=self.options.lines,
            )

            self._stream_logs()

        except KeyboardInterrupt:
            self._handle_stop()
        except Exception as e:
            self.handle_error(e, "Failed to fetch logs")
            raise SystemExit(1)

    def _find_container(self, ssh_service, vm_ip: str) -> Optional[str]:
        """
        Find container by Superdeploy labels.

        Uses Superdeploy custom labels to find the exact container:
        - com.superdeploy.project={project_name}
        - com.superdeploy.app={app_name}
        """
        # Try to find by Superdeploy labels
        cmd = (
            f'docker ps --filter "label=com.superdeploy.project={self.project_name}" '
            f'--filter "label=com.superdeploy.app={self.options.app_name}" '
            '--format "{{.Names}}" | head -1'
        )

        result = ssh_service.execute_command(vm_ip, cmd)

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        return None

    def _print_header(self) -> None:
        """Print logs header with filters."""
        filters = []
        if self.options.filter_level:
            filters.append(f"level={self.options.filter_level}")
        if self.options.grep_pattern:
            filters.append(f"grep='{self.options.grep_pattern}'")

        filter_str = f" | {', '.join(filters)}" if filters else ""

        self.console.print()
        self.console.print(
            f"[bold cyan]📋 {self.project_name}/{self.options.app_name}[/bold cyan]",
            end="",
        )
        self.console.print(f" [dim](streaming{filter_str})[/dim]")
        self.console.print()

    def _stream_logs(self) -> None:
        """Stream and filter log output."""
        if not self.process or not self.process.stdout:
            return

        for line in self.process.stdout:
            if not line.strip():
                continue

            # Parse log line
            parsed = self.parser.parse(line)

            # Apply filters
            if not self.filter.matches(parsed, line):
                continue

            # Colorize and print
            colored_line = self.colorizer.colorize(parsed)
            print(colored_line)
            self.line_count += 1

        self.process.wait()

    def _handle_stop(self) -> None:
        """Handle stopping log stream."""
        self.console.print(
            f"\n[dim]✓ Stopped (displayed {self.line_count} lines)[/dim]"
        )
        if self.process:
            self.process.terminate()


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, storefront, services)")
@click.option(
    "-n",
    "--lines",
    default=100,
    help="Number of recent lines to show before streaming",
)
@click.option("--level", help="Filter by log level (ERROR, WARNING, INFO, DEBUG)")
@click.option("--grep", "grep_pattern", help="Filter logs by pattern (supports regex)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def logs(project, app, lines, level, grep_pattern, verbose, json_output):
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
    options = LogsOptions(
        app_name=app,
        lines=lines,
        filter_level=level,
        grep_pattern=grep_pattern,
    )

    cmd = LogsCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
