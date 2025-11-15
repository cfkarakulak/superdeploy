"""
Base Command Class

Abstract base for all SuperDeploy CLI commands.
Provides common functionality and structure.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
import json
from rich.console import Console
from cli.ui_components import show_header
from cli.logger import DeployLogger
from cli.utils import get_project_root


class BaseCommand(ABC):
    """
    Abstract base command class.

    Provides:
    - Logger initialization
    - Header display
    - Error handling
    - Common utilities
    - Consistent structure
    - JSON output support
    """

    def __init__(self, verbose: bool = False, json_output: bool = False):
        self.verbose = verbose
        self.json_output = json_output
        self.console = Console()
        self.project_root = get_project_root()
        self.logger: Optional[DeployLogger] = None

    def init_logger(
        self, project_name: str, command_name: str
    ) -> Optional[DeployLogger]:
        """
        Initialize command logger (skip in JSON mode).

        Args:
            project_name: Project name (use "global" for non-project commands)
            command_name: Command name

        Returns:
            DeployLogger instance or None if JSON mode
        """
        if self.json_output:
            return None
        self.logger = DeployLogger(project_name, command_name, verbose=self.verbose)
        return self.logger

    def output_json(self, data: Dict[str, Any], exit_code: int = 0) -> None:
        """
        Output data as JSON and exit.

        Args:
            data: Data to output as JSON
            exit_code: Exit code (0 for success, non-zero for error)
        """
        print(json.dumps(data, indent=2))
        if exit_code != 0:
            raise SystemExit(exit_code)

    def output_json_error(
        self, error: str, details: Optional[Dict[str, Any]] = None, exit_code: int = 1
    ) -> None:
        """
        Output error as JSON and exit.

        Args:
            error: Error message
            details: Optional error details
            exit_code: Exit code
        """
        error_data = {"error": error}
        if details:
            error_data["details"] = details
        self.output_json(error_data, exit_code=exit_code)

    def show_header(
        self,
        title: str,
        subtitle: Optional[str] = None,
        project: Optional[str] = None,
        app: Optional[str] = None,
        details: Optional[dict] = None,
        border_color: str = "cyan",
        show_logo: bool = False,
    ) -> None:
        """
        Show command header (skip in JSON or verbose mode).

        Args:
            title: Header title
            subtitle: Optional subtitle
            project: Project name
            app: App name
            details: Additional details dict
            border_color: Border color
            show_logo: Show SuperDeploy logo
        """
        if not self.verbose and not self.json_output:
            show_header(
                title=title,
                subtitle=subtitle,
                project=project,
                app=app,
                details=details,
                border_color=border_color,
                show_logo=show_logo,
                console=self.console,
            )

    def print_success(self, message: str) -> None:
        """Print success message (skip in JSON mode)."""
        if not self.json_output:
            self.console.print(f"[green]✓ {message}[/green]")

    def print_error(self, message: str) -> None:
        """Print error message (skip in JSON mode)."""
        if not self.json_output:
            self.console.print(f"[red]✗ {message}[/red]")

    def print_warning(self, message: str) -> None:
        """Print warning message (skip in JSON mode)."""
        if not self.json_output:
            self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def print_dim(self, message: str) -> None:
        """Print dim message (skip in JSON mode)."""
        if not self.json_output:
            self.console.print(f"[dim]{message}[/dim]")

    def confirm(self, question: str, default: bool = False) -> bool:
        """
        Ask for user confirmation.

        Args:
            question: Question to ask
            default: Default answer

        Returns:
            True if confirmed
        """
        default_str = "y" if default else "n"
        self.console.print(
            f"{question} [bold bright_white]\\[y/n][/bold bright_white] [dim]({default_str})[/dim]: ",
            end="",
        )
        answer = input().strip().lower()

        if not answer:
            return default

        return answer in ["y", "yes"]

    def handle_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Handle error with consistent formatting.

        Args:
            error: Exception object
            context: Optional context message
        """
        if self.logger:
            self.logger.log_error(str(error), context=context)
        else:
            self.print_error(str(error))
            if context:
                self.print_dim(f"Context: {context}")

    def exit_with_error(self, message: str, code: int = 1) -> None:
        """
        Print error and exit.

        Args:
            message: Error message
            code: Exit code
        """
        self.print_error(message)
        raise SystemExit(code)

    @abstractmethod
    def execute(self, **kwargs) -> None:
        """
        Execute command logic.

        Must be implemented by subclasses.
        """
        pass

    def run(self, **kwargs) -> None:
        """
        Run command with error handling.

        Args:
            **kwargs: Command arguments
        """
        try:
            self.execute(**kwargs)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️  Operation cancelled by user[/yellow]")
            if self.logger:
                self.console.print(
                    f"\n[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(130)
        except SystemExit:
            raise
        except FileNotFoundError as e:
            self.console.print(f"\n[bold red]✗ File not found:[/bold red] {e}\n")
            if self.logger:
                self.logger.log_error(f"File not found: {e}")
                self.console.print(
                    f"[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(1)
        except PermissionError as e:
            self.console.print(f"\n[bold red]✗ Permission denied:[/bold red] {e}\n")
            self.console.print("[dim]Try running with appropriate permissions[/dim]\n")
            if self.logger:
                self.logger.log_error(f"Permission error: {e}")
                self.console.print(
                    f"[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(1)
        except ValueError as e:
            self.console.print(f"\n[bold red]✗ Invalid value:[/bold red] {e}\n")
            if self.logger:
                self.logger.log_error(f"Value error: {e}")
                self.console.print(
                    f"[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(1)
        except Exception as e:
            # Generic error handling
            error_type = type(e).__name__
            self.console.print(f"\n[bold red]✗ {error_type}:[/bold red] {e}\n")
            if self.logger:
                self.logger.log_error(f"{error_type}: {e}")
                self.console.print(
                    f"[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(1)
