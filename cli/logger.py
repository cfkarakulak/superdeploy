"""
Logging system for SuperDeploy CLI
Provides real-time logging to files with clean console output
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, TextIO
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

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
{'=' * 80}
SuperDeploy Deployment Log
{'=' * 80}
Project: {self.project_name}
Operation: {self.operation}
Started: {datetime.now().isoformat()}
{'=' * 80}

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

        Args:
            output: Command output
            stream: Stream name (stdout, stderr)
        """
        if not output:
            return

        # Write to log file with stream indicator
        for line in output.splitlines():
            self.log_file.write(f"  [{stream}] {line}\n")
        self.log_file.flush()

        # Show in console if verbose
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
{'!' * 80}
ERROR OCCURRED
{'!' * 80}
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

        console.print(
            Panel(
                f"[bold red]{error}[/bold red]"
                + (f"\n\n[dim]{context}[/dim]" if context else ""),
                title="[bold red]❌ Error[/bold red]",
                border_style="red",
            )
        )

        # Show log file location
        console.print(f"\n[dim]Full logs:[/dim] {self.log_path}\n")

    def step(self, step_name: str):
        """
        Start a new step

        Args:
            step_name: Name of the step
        """
        self.current_step = step_name
        self.log(f"Step: {step_name}", "INFO")

        if not self.verbose:
            console.print(f"\n[cyan]▶[/cyan] {step_name}")

    def success(self, message: str):
        """Log a success message"""
        self.log(message, "INFO")

        if not self.verbose:
            console.print(f"[green]✓[/green] {message}")

    def warning(self, message: str):
        """Log a warning message"""
        self.log(message, "WARNING")

        if not self.verbose:
            console.print(f"[yellow]⚠[/yellow] {message}")

    def close(self):
        """Close log file"""
        if self.log_file:
            # Write footer
            footer = f"""
{'=' * 80}
Completed: {datetime.now().isoformat()}
Status: {'FAILED' if self.has_errors else 'SUCCESS'}
{'=' * 80}
"""
            self.log_file.write(footer)
            self.log_file.close()
            self.log_file = None

        # Show summary
        if not self.verbose:
            if self.has_errors:
                console.print(
                    f"\n[red]✗[/red] Operation failed. Check logs: {self.log_path}\n"
                )
            else:
                console.print(f"\n[dim]Logs saved to:[/dim] {self.log_path}\n")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            # Log unhandled exception
            self.log_error(
                f"Unhandled exception: {exc_val}", context=f"Type: {exc_type.__name__}"
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
        # Verbose mode: show output directly
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=False, text=True
        )
        return result.returncode, "", ""

    # Non-verbose: show spinner, capture output
    with Live(
        Spinner("dots", text=f"[cyan]{description}...[/cyan]"),
        console=console,
        refresh_per_second=10,
    ) as live:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True
        )

        # Log output
        if result.stdout:
            logger.log_output(result.stdout, "stdout")
        if result.stderr:
            logger.log_output(result.stderr, "stderr")

        # Update live display
        if result.returncode == 0:
            live.update(Text(f"✓ {description}", style="green"))
        else:
            live.update(Text(f"✗ {description}", style="red"))

    return result.returncode, result.stdout, result.stderr
