"""
Base Command Class

Abstract base for all SuperDeploy CLI commands.
Provides common functionality and structure.
"""

from abc import ABC, abstractmethod
from typing import Optional
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
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.console = Console()
        self.project_root = get_project_root()
        self.logger: Optional[DeployLogger] = None

    def init_logger(self, project_name: str, command_name: str) -> DeployLogger:
        """
        Initialize command logger.

        Args:
            project_name: Project name (use "global" for non-project commands)
            command_name: Command name

        Returns:
            DeployLogger instance
        """
        self.logger = DeployLogger(project_name, command_name, verbose=self.verbose)
        return self.logger

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
        Show command header (only if not verbose).

        Args:
            title: Header title
            subtitle: Optional subtitle
            project: Project name
            app: App name
            details: Additional details dict
            border_color: Border color
            show_logo: Show SuperDeploy logo
        """
        if not self.verbose:
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
        """Print success message."""
        self.console.print(f"[green]✓ {message}[/green]")

    def print_error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"[red]✗ {message}[/red]")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def print_info(self, message: str) -> None:
        """Print info message."""
        self.console.print(f"[cyan]ℹ {message}[/cyan]")

    def print_dim(self, message: str) -> None:
        """Print dim message."""
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
            self.print_warning("Interrupted by user")
            if self.logger:
                self.console.print(
                    f"\n[dim]Logs saved to:[/dim] {self.logger.log_path}\n"
                )
            raise SystemExit(0)
        except SystemExit:
            raise
        except Exception as e:
            self.handle_error(e)
            raise SystemExit(1)

