"""
SuperDeploy CLI - UI Components & Branding
Standardized headers, logos, and UI elements
"""

from rich.console import Console

LOGO = "superdeploy"

# Color scheme
BRAND_COLOR = "cyan"
SUCCESS_COLOR = "green"
WARNING_COLOR = "yellow"
ERROR_COLOR = "red"
INFO_COLOR = "blue"


def show_header(
    title: str,
    subtitle: str = None,
    project: str = None,
    app: str = None,
    details: dict = None,
    show_logo: bool = True,
    border_color: str = None,
    console: Console = None,
):
    """
    Display a standardized SuperDeploy command header with ASCII logo.

    Args:
        title: Main title (e.g., "Run Command", "Deploy Infrastructure")
        subtitle: Optional subtitle line
        project: Project name (if applicable)
        app: App name (if applicable)
        details: Additional key-value pairs to display
        show_logo: Deprecated - ASCII logo is always shown
        border_color: Panel border color (default: cyan)
        console: Rich Console instance (creates new if None)

    Example:
        show_header(
            title="Run Command",
            project="cheapa",
            app="api",
            details={"Command": "bash", "Mode": "Interactive"}
        )
    """
    if console is None:
        console = Console()

    if border_color is None:
        border_color = BRAND_COLOR

    # Heroku-style minimal header
    console.print(
        f" [bold color(214)]superdeploy[/bold color(214)] [dim]›[/dim] [bold white]{title}[/bold white]"
    )

    # Subtitle
    if subtitle:
        console.print(
            f" [bold color(214)]superdeploy[/bold color(214)] [dim]›[/dim] [dim]{subtitle}[/dim]"
        )

    # Project/App info
    if project:
        console.print(
            f" [bold color(214)]superdeploy[/bold color(214)] [dim]›[/dim] Project: [cyan]{project}[/cyan]"
        )
    if app:
        console.print(
            f" [bold color(214)]superdeploy[/bold color(214)] [dim]›[/dim] App: [cyan]{app}[/cyan]"
        )

    # Additional details
    if details:
        for key, value in details.items():
            console.print(
                f" [bold color(214)]superdeploy[/bold color(214)] [dim]›[/dim] {key}: [cyan]{value}[/cyan]"
            )

    # Single blank line after header
    console.print()


def show_success(message: str, console: Console = None):
    """Display a success message with branding."""
    if console is None:
        console = Console()

    console.print(f"\n[{SUCCESS_COLOR}]✅ {message}[/{SUCCESS_COLOR}]")


def show_error(message: str, console: Console = None):
    """Display an error message with branding."""
    if console is None:
        console = Console()

    console.print(f"\n[{ERROR_COLOR}]✗ {message}[/{ERROR_COLOR}]")


def show_warning(message: str, console: Console = None):
    """Display a warning message with branding."""
    if console is None:
        console = Console()

    console.print(f"\n[{WARNING_COLOR}]⚠ {message}[/{WARNING_COLOR}]")


def show_info(message: str, console: Console = None):
    """Display an info message with branding."""
    if console is None:
        console = Console()

    console.print(f"\n[{INFO_COLOR}]ℹ {message}[/{INFO_COLOR}]")


def show_logo_full(console: Console = None):
    """Display the full SuperDeploy ASCII logo."""
    if console is None:
        console = Console()

    console.print(f"[bold {BRAND_COLOR}]{LOGO}[/bold {BRAND_COLOR}]")
    console.print(
        "[dim]Deploy production apps like Heroku, on your own infrastructure[/dim]\n"
    )
