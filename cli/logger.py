"""
Logging system for SuperDeploy CLI
Provides real-time logging to files with clean console output
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, TextIO
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.padding import Padding

console = Console()


class DeployLogger:
    """
    Manages logging for deployment operations
    - Writes all output to log files in real-time
    - Shows clean progress UI in console (unless verbose)
    - Captures errors with context
    """

    def __init__(self, project_name: str, operation: str, verbose: bool = False):
        """
        Initialize logger

        Args:
            project_name: Name of project (or 'orchestrator')
            operation: Operation name (e.g., 'up', 'down', 'init')
            verbose: If True, show all output in console
        """
        self.project_name = project_name
        self.operation = operation
        self.verbose = verbose
        self.log_file: Optional[TextIO] = None
        self.log_path: Optional[Path] = None
        self.current_step = ""
        self.has_errors = False

        # Create organized logs directory structure
        from cli.utils import get_project_root

        project_root = get_project_root()

        # Structure: logs/{project}/{date}/{time}_{operation}.log
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")

        project_logs_dir = project_root / "logs" / project_name / date_str
        project_logs_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with time and operation
        log_filename = f"{time_str}_{operation}.log"
        self.log_path = project_logs_dir / log_filename

        # Open log file for writing (unbuffered for real-time)
        self.log_file = open(self.log_path, "w", buffering=1)

        # Write header
        self._write_log_header()

    def _write_log_header(self):
        """Write log file header"""
        header = f"""
{"=" * 80}
SuperDeploy Deployment Log
{"=" * 80}
Project: {self.project_name}
Operation: {self.operation}
Started: {datetime.now().isoformat()}
{"=" * 80}

"""
        self.log_file.write(header)
        self.log_file.flush()

    def log(self, message: str, level: str = "INFO"):
        """
        Log a message to file and optionally console

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR, DEBUG)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}\n"

        # Write to file (real-time)
        if self.log_file:
            self.log_file.write(log_line)
            self.log_file.flush()

        # Show in console if verbose
        if self.verbose:
            if level == "ERROR":
                console.print(f"[red]{message}[/red]")
            elif level == "WARNING":
                console.print(f"[yellow]{message}[/yellow]")
            elif level == "DEBUG":
                console.print(f"[dim]{message}[/dim]")
            else:
                console.print(message)

    def log_command(self, command: str):
        """Log a command being executed"""
        self.log(f"Executing: {command}", "DEBUG")

    def log_output(self, output: str, stream: str = "stdout"):
        """
        Log command output

        IMPORTANT: This method ALWAYS writes to log file (regardless of verbose mode)
        but only shows in console if verbose=True

        Args:
            output: Command output (single line or multiline)
            stream: Stream name (stdout, stderr)
        """
        if not output:
            return

        # Strip ANSI color codes for log file
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_output = ansi_escape.sub("", output)

        # ALWAYS write to log file (regardless of verbose mode)
        if self.log_file:
            try:
                # Handle both single line and multiline output
                if "\n" in clean_output:
                    for line in clean_output.splitlines():
                        self.log_file.write(f"  [{stream}] {line}\n")
                else:
                    self.log_file.write(f"  [{stream}] {clean_output}\n")

                # Flush periodically, but don't block terminal
                # OS will eventually flush even if this fails
                try:
                    self.log_file.flush()
                except (BlockingIOError, OSError, IOError):
                    pass  # Skip flush if it would block
            except (BlockingIOError, OSError, IOError):
                # If write itself would block, skip this batch
                # Terminal responsiveness is more important
                pass

        # Show in console ONLY if verbose (caller handles console output otherwise)
        # Note: Most callers (like AnsibleRunner) print to console themselves
        # This is just a fallback for direct log_output() calls
        if self.verbose:
            console.print(output)

    def log_error(self, error: str, context: Optional[str] = None):
        """
        Log an error with context

        Args:
            error: Error message
            context: Additional context (e.g., command that failed)
        """
        self.has_errors = True

        # Write to log with clear markers for grepping
        error_block = f"""
{"!" * 80}
ERROR OCCURRED
{"!" * 80}
{error}
"""
        if context:
            error_block += f"\nContext: {context}\n"

        error_block += f"{'!' * 80}\n\n"

        self.log_file.write(error_block)
        self.log_file.flush()

        # Show in console (always, even if not verbose)
        if not self.verbose:
            console.print()  # Add spacing

        # Clean, elegant error display without box
        console.print(f"[bold red]✗ {error}[/bold red]")
        if context:
            console.print(f"  [color(208)]{context}[/color(208)]")

    def step(self, step_name: str):
        """
        Start a new step

        Args:
            step_name: Name of the step
        """
        # Add spacing between steps (but not before the first step)
        if self.current_step and not self.verbose:
            console.print()

        self.current_step = step_name
        self.log(f"Step: {step_name}", "INFO")

        if not self.verbose:
            console.print(f"[color(214)]▶[/color(214)] [white]{step_name}[/white]")

    def success(self, message: str):
        """Log a success message"""
        self.log(message, "INFO")

        if not self.verbose:
            console.print(f"  [dim]✓ {message}[/dim]")

    def warning(self, message: str):
        """Log a warning message"""
        self.log(message, "WARNING")

        if not self.verbose:
            console.print(f"  [yellow]⚠[/yellow] [dim]{message}[/dim]")

    def close(self):
        """Close log file"""
        if self.log_file:
            # Write footer
            footer = f"""
{"=" * 80}
Completed: {datetime.now().isoformat()}
Status: {"FAILED" if self.has_errors else "SUCCESS"}
{"=" * 80}
"""
            self.log_file.write(footer)
            self.log_file.close()
            self.log_file = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        """Context manager exit"""
        if exc_type is not None and exc_type != SystemExit:
            # Log unhandled exception (but not SystemExit - that's expected)
            self.log_error(
                str(exc_val) if exc_val else "Operation failed",
                context=f"{exc_type.__name__}",
            )
        self.close()
        return False  # Don't suppress exceptions


def run_with_progress(
    logger: DeployLogger, command: str, description: str, cwd: Optional[Path] = None
) -> tuple[int, str, str]:
    """
    Run a command with progress indicator

    Args:
        logger: DeployLogger instance
        command: Command to run
        description: Description for progress indicator
        cwd: Working directory

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    import subprocess

    logger.log_command(command)

    if logger.verbose:
        # Verbose mode: capture output for logging, show in real-time
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        # Read stdout
        if process.stdout:
            for line in process.stdout:
                line_stripped = line.rstrip()
                stdout_lines.append(line_stripped)
                # Log to file
                logger.log_output(line_stripped, "stdout")
                # Show in console
                print(line_stripped)

        # Wait for process and get stderr
        process.wait()
        if process.stderr:
            stderr_content = process.stderr.read()
            if stderr_content:
                stderr_lines = stderr_content.splitlines()
                for line in stderr_lines:
                    logger.log_output(line, "stderr")
                    print(line)

        return process.returncode, "\n".join(stdout_lines), "\n".join(stderr_lines)

    # Non-verbose: show spinner, capture output
    spinner = Spinner("dots", text=f"[cyan]{description}...[/cyan]")
    padded_spinner = Padding(spinner, (0, 0, 0, 2))  # left padding of 2 spaces

    with Live(
        padded_spinner,
        console=console,
        refresh_per_second=10,
    ) as live:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True
        )

        # ALWAYS log output to file (regardless of verbose mode)
        if result.stdout:
            logger.log_output(result.stdout, "stdout")
        if result.stderr:
            logger.log_output(result.stderr, "stderr")

        # Update live display with proper formatting
        if result.returncode == 0:
            # Entire line is dim (including checkmark)
            checkmark = Text("  ✓ ", style="dim")
            checkmark.append(description, style="dim")
            live.update(checkmark)
        else:
            # Only X is red, description is dim
            x_mark = Text("  ✗ ", style="red")
            x_mark.append(description, style="dim")
            live.update(x_mark)

    return result.returncode, result.stdout, result.stderr
