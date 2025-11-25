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

    app_name: Optional[str] = None  # Optional: if None, show all project containers
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
        self.processes: list[
            tuple[str, subprocess.Popen]
        ] = []  # For multi-process streaming

    def execute(self) -> None:
        """Execute logs command."""
        self._print_header()
        self.require_deployment()

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # If app_name is None, show logs from ALL project containers across ALL VMs
        if self.options.app_name is None:
            containers_by_vm = self._find_all_project_containers(ssh_service)
            if not containers_by_vm:
                raise Exception(
                    f"No containers found for project {self.project_name}. "
                    f"Make sure the project is running."
                )
        else:
            # Get VM and IP for specific app
            try:
                vm_name, vm_ip = self.get_vm_for_app(self.options.app_name)
            except Exception as e:
                self.handle_error(e)
                raise SystemExit(1)

            # Find ALL containers for this app (all processes: web, worker, etc.)
            containers = self._find_all_containers(ssh_service, vm_ip)

            if not containers:
                raise Exception(
                    f"No containers found for {self.project_name}/{self.options.app_name}. "
                    f"Make sure the app is running."
                )

            containers_by_vm = {vm_ip: containers}

        try:
            # Count total containers
            total_containers = sum(
                len(containers) for containers in containers_by_vm.values()
            )

            if total_containers > 1:
                self.console.print(
                    f"[dim]→ Streaming logs from {total_containers} containers across {len(containers_by_vm)} VM(s)... Press Ctrl+C to stop[/dim]\n"
                )
            else:
                container_name = list(containers_by_vm.values())[0][0]
                self.console.print(
                    f"[dim]→ Streaming logs from {container_name}... Press Ctrl+C to stop[/dim]\n"
                )

            # Start streaming logs from all containers across all VMs
            self.processes = []
            for vm_ip, containers in containers_by_vm.items():
                for container_name in containers:
                    process = ssh_service.docker_logs(
                        vm_ip,
                        container_name,
                        follow=self.options.follow,
                        tail=self.options.lines,
                    )
                    self.processes.append((container_name, process))

            # Give it a moment to start
            import time

            time.sleep(0.5)

            # Check if any process started successfully
            all_failed = True
            for container_name, process in self.processes:
                if process.poll() is None:
                    all_failed = False
                    break

            if all_failed:
                error_messages = []
                for container_name, process in self.processes:
                    error_output = process.stderr.read() if process.stderr else b""
                    if error_output:
                        error_msg = error_output.decode("utf-8", errors="ignore")
                        error_messages.append(f"{container_name}: {error_msg}")
                raise Exception(
                    f"Failed to start log streams: {'; '.join(error_messages)}"
                )

            self._stream_logs_multi()

        except KeyboardInterrupt:
            self._handle_stop()
        except Exception as e:
            self.handle_error(e, "Failed to fetch logs")
            raise SystemExit(1)

    def _find_all_project_containers(self, ssh_service) -> dict[str, list[str]]:
        """
        Find ALL containers for this project across ALL VMs.

        Returns dict of {vm_ip: [container_names]}
        """
        containers_by_vm = {}

        # Get all VMs for this project
        state = self.state_service.load_state()

        for vm_name, vm_data in state.vms.items():
            # Use external IP for SSH connections (internal IPs are not accessible)
            vm_ip = vm_data.external_ip
            if not vm_ip:
                continue

            # Find all project containers on this VM (excluding superdeploy infra)
            # Strategy: Find both addon containers (project_name_*) and app containers (compose-*)
            cmd = f'docker ps --format "{{{{.Names}}}}" | grep -E "^{self.project_name}_|^compose-" || true'
            result = ssh_service.execute_command(vm_ip, cmd, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                found_containers = result.stdout.strip().split("\n")
                containers = [
                    c.strip()
                    for c in found_containers
                    if c.strip() and "superdeploy-" not in c
                ]
                if containers:
                    containers_by_vm[vm_ip] = containers

        return containers_by_vm

    def _find_all_containers(self, ssh_service, vm_ip: str) -> list[str]:
        """
        Find ALL containers for this app (all processes: web, worker, etc.).

        Returns list of container names.
        """
        containers = []

        # Strategy 1: Find by Docker Compose pattern (compose-{app}-{process}-{replica})
        # This will find all processes: web, worker, etc.
        cmd = f'docker ps --filter "name=compose-{self.options.app_name}-" --format "{{{{.Names}}}}"'
        result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            found_containers = result.stdout.strip().split("\n")
            containers.extend([c.strip() for c in found_containers if c.strip()])
            if containers:
                self.console.print(
                    f"[dim]Found {len(containers)} containers by pattern: {', '.join(containers)}[/dim]"
                )
                return containers

        # Strategy 2: Try Superdeploy labels
        cmd = (
            f'docker ps --filter "label=com.superdeploy.project={self.project_name}" '
            f'--filter "label=com.superdeploy.app={self.options.app_name}" '
            '--format "{{.Names}}"'
        )
        result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            found_containers = result.stdout.strip().split("\n")
            containers.extend([c.strip() for c in found_containers if c.strip()])
            if containers:
                self.console.print(
                    f"[dim]Found {len(containers)} containers by labels: {', '.join(containers)}[/dim]"
                )
                return containers

        # Strategy 3: List all containers and match by app name
        cmd = 'docker ps --format "{{.Names}}"'
        result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

        if result.returncode == 0:
            all_containers = result.stdout.strip().split("\n")
            for container in all_containers:
                container = container.strip()
                if container and self.options.app_name.lower() in container.lower():
                    if container not in containers:
                        containers.append(container)

        if containers:
            self.console.print(
                f"[dim]Found {len(containers)} containers by name match: {', '.join(containers)}[/dim]"
            )

        return containers

    def _find_container(self, ssh_service, vm_ip: str) -> Optional[str]:
        """
        Find container by Superdeploy labels or Docker Compose naming.

        Uses multiple strategies:
        1. Superdeploy custom labels
        2. Docker Compose naming pattern: compose-{app}-{process}-{replica}
        3. Direct container name match
        """
        # Strategy 1: Try Superdeploy labels
        cmd = (
            f'docker ps --filter "label=com.superdeploy.project={self.project_name}" '
            f'--filter "label=com.superdeploy.app={self.options.app_name}" '
            '--format "{{.Names}}" | head -1'
        )

        result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            container_name = result.stdout.strip()
            self.console.print(
                f"[dim]Found container by labels: {container_name}[/dim]"
            )
            return container_name

        # Strategy 2: Try Docker Compose naming pattern
        # Pattern: compose-{app}-{process}-{replica}
        # We'll try web process first, then any process
        compose_patterns = [
            f"compose-{self.options.app_name}-web-1",
            f"compose-{self.options.app_name}-web-",
            f"compose-{self.options.app_name}-",
        ]

        for pattern in compose_patterns:
            cmd = f'docker ps --filter "name={pattern}" --format "{{{{.Names}}}}" | head -1'
            result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

            if result.returncode == 0 and result.stdout.strip():
                container_name = result.stdout.strip()
                self.console.print(
                    f"[dim]Found container by pattern: {container_name}[/dim]"
                )
                return container_name

        # Strategy 3: List all containers and try to match
        cmd = 'docker ps --format "{{.Names}}"'
        result = ssh_service.execute_command(vm_ip, cmd, timeout=5)

        if result.returncode == 0:
            containers = result.stdout.strip().split("\n")
            for container in containers:
                if self.options.app_name.lower() in container.lower():
                    self.console.print(
                        f"[dim]Found container by name match: {container}[/dim]"
                    )
                    return container.strip()

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
        if self.options.app_name:
            self.console.print(
                f"[bold cyan]📋 {self.project_name}/{self.options.app_name}[/bold cyan]",
                end="",
            )
        else:
            self.console.print(
                f"[bold cyan]📋 {self.project_name} (all containers)[/bold cyan]",
                end="",
            )
        self.console.print(f" [dim](streaming{filter_str})[/dim]")
        self.console.print()

    def _stream_logs_multi(self) -> None:
        """Stream logs from multiple containers - simple multiplexing."""
        if not hasattr(self, "processes") or not self.processes:
            return

        import select

        # Simple select-based multiplexing
        try:
            while True:
                # Check if all processes ended
                if all(proc.poll() is not None for _, proc in self.processes):
                    break

                # Get active streams
                streams = [(name, proc.stdout) for name, proc in self.processes 
                          if proc.poll() is None and proc.stdout]

                if not streams:
                    break

                # Wait for data
                try:
                    ready_streams = [s for _, s in streams]
                    ready, _, _ = select.select(ready_streams, [], [], 0.1)
                except (OSError, ValueError):
                    import time
                    time.sleep(0.1)
                    continue

                # Read from ready streams
                for container_name, stream in streams:
                    if stream in ready:
                        line = stream.readline()
                        if not line:
                            continue
                            
                        line_str = line.decode("utf-8", errors="ignore").strip()
                        if not line_str:
                            continue

                        # Prefix for multi-container
                        prefix = f"[{container_name}] " if len(self.processes) > 1 else ""

                        # Parse, filter, colorize
                        parsed = self.parser.parse(line_str)
                        if not self.filter.matches(parsed, line_str):
                            continue

                        colored_line = self.colorizer.colorize(parsed)
                        print(f"{prefix}{colored_line}", flush=True)
                        self.line_count += 1

        except KeyboardInterrupt:
            raise
        finally:
            for _, proc in self.processes:
                if proc.poll() is None:
                    proc.terminate()

    def _stream_logs(self) -> None:
        """Stream logs from a single container - simple & instant."""
        if not hasattr(self, "process") or not self.process or not self.process.stdout:
            return

        # Simple readline loop - like Heroku
        try:
            for line in iter(self.process.stdout.readline, b''):
                if not line:
                    break

                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue

                # Parse, filter, colorize
                parsed = self.parser.parse(line_str)
                if not self.filter.matches(parsed, line_str):
                    continue

                colored_line = self.colorizer.colorize(parsed)
                print(colored_line, flush=True)
                self.line_count += 1

        except KeyboardInterrupt:
            raise
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def _handle_stop(self) -> None:
        """Handle stopping log stream."""
        self.console.print(
            f"\n[dim]✓ Stopped (displayed {self.line_count} lines)[/dim]"
        )
        # Stop all processes
        if hasattr(self, "processes") and self.processes:
            for container_name, process in self.processes:
                if process.poll() is None:
                    process.terminate()
        elif self.process:
            self.process.terminate()


@click.command()
@click.option(
    "-a",
    "--app",
    required=False,
    help="App name (api, storefront, services). If omitted, shows all project containers",
)
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
    - If -a is omitted, streams ALL project containers across ALL VMs

    Examples:
        # Stream logs from ALL project containers
        superdeploy cheapa:logs

        # Stream logs from specific app (starts from last 100 lines)
        superdeploy cheapa:logs -a api

        # Stream from last 500 lines
        superdeploy cheapa:logs -a api -n 500

        # Only show errors while streaming (all containers)
        superdeploy cheapa:logs --level ERROR

        # Search for specific pattern across all containers
        superdeploy cheapa:logs --grep "database"

        # Combine filters (grep + level)
        superdeploy cheapa:logs -a api --grep "GET.*200" --level INFO

        # Monitor errors in real-time from all containers
        superdeploy cheapa:logs --level ERROR
    """
    options = LogsOptions(
        app_name=app,
        lines=lines,
        filter_level=level,
        grep_pattern=grep_pattern,
    )

    cmd = LogsCommand(project, options, verbose=verbose, json_output=json_output)
    cmd.run()
