"""
SuperDeploy CLI - UI Components & Branding
Standardized headers, logos, and UI elements
"""

from rich.console import Console
from rich.panel import Panel

# ASCII Art Logo
LOGO = r"""
   _____                       ____             __          
  / ___/__  ______  ___  _____/ __ \___  ____  / /___  __  __
  \__ \/ / / / __ \/ _ \/ ___/ / / / _ \/ __ \/ / __ \/ / / /
 ___/ / /_/ / /_/ /  __/ /  / /_/ /  __/ /_/ / / /_/ / /_/ / 
/____/\__,_/ .___/\___/_/  /_____/\___/ .___/_/\____/\__, /  
          /_/                        /_/            /____/   
"""

LOGO_COMPACT = "🚀 SuperDeploy"

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
    show_logo: bool = False,
    border_color: str = None,
    console: Console = None,
):
    """
    Display a standardized SuperDeploy command header.

    Args:
        title: Main title (e.g., "Run Command", "Deploy Infrastructure")
        subtitle: Optional subtitle line
        project: Project name (if applicable)
        app: App name (if applicable)
        details: Additional key-value pairs to display
        show_logo: Show full ASCII logo (for major operations)
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

    # Build header content
    lines = []

    # Logo (for major operations)
    if show_logo:
        lines.append(f"[dim]{LOGO}[/dim]")
        lines.append("")
    else:
        # Compact logo with title
        lines.append(
            f"[bold {BRAND_COLOR}]{LOGO_COMPACT} • {title}[/bold {BRAND_COLOR}]"
        )

    # Subtitle
    if subtitle:
        lines.append("")
        lines.append(f"[white]{subtitle}[/white]")

    # Project/App info (common fields)
    if project or app or details:
        lines.append("")

    if project:
        lines.append(f"[white]Project:[/white] [bold]{project}[/bold]")

    if app:
        lines.append(f"[white]App:[/white] [bold]{app}[/bold]")

    # Additional details
    if details:
        for key, value in details.items():
            lines.append(f"[white]{key}:[/white] [bold]{value}[/bold]")

    # Create panel
    content = "\n".join(lines)
    panel = Panel.fit(
        content,
        border_style=border_color,
        padding=(0, 1),
    )

    console.print(panel)
    console.print()  # Extra line after header


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
