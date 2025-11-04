"""SuperDeploy CLI - Secure env viewing command"""

import click
import getpass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from cli.utils import load_env

console = Console()


def get_addon_prefixes(project):
    """
    Get environment variable prefixes from addon metadata.

    Args:
        project (str): Project name

    Returns:
        list: List of environment variable prefixes
    """
    from cli.core.addon_loader import AddonLoader
    from cli.utils import get_project_root

    try:
        project_root = get_project_root()
        addons_dir = project_root / "addons"
        addon_loader = AddonLoader(addons_dir)

        # Load project config to get enabled addons
        from cli.core.config_loader import ConfigLoader

        projects_dir = project_root / "projects"
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)

        # Load addons
        addons = addon_loader.load_addons_for_project(project_config.raw_config)

        # Extract prefixes from env var names
        prefixes = set()
        for addon_name, addon in addons.items():
            for var_name in addon.get_env_var_names():
                # Extract prefix (e.g., "POSTGRES_HOST" -> "POSTGRES")
                prefix = var_name.split("_")[0]
                prefixes.add(prefix)

        # Add app-specific prefixes
        prefixes.update(["API", "SENTRY"])

        return list(prefixes)
    except Exception as e:
        # Fallback to common prefixes if addon loading fails
        console.print(f"[dim]Could not load addon prefixes: {e}[/dim]")
        return ["POSTGRES", "RABBITMQ", "REDIS", "API", "SENTRY"]


def verify_password(env_vars):
    """Verify user identity with password challenge"""
    # Use GITHUB_TOKEN as verification (secure and already in .env)
    expected_token = env_vars.get("GITHUB_TOKEN", "")

    if not expected_token or expected_token in ["", "your-github-token"]:
        console.print("[red]❌ GITHUB_TOKEN not configured in .env[/red]")
        console.print("[yellow]Set a valid GITHUB_TOKEN to use --no-mask[/yellow]")
        return False

    console.print(
        Panel(
            "[yellow]⚠️  Sensitive data access[/yellow]\n\n"
            "[white]Enter your GITHUB_TOKEN (from .env):[/white]",
            border_style="yellow",
        )
    )

    password = getpass.getpass("Token: ")

    # Verify token matches
    if password.strip() != expected_token.strip():
        console.print("[red]❌ Access denied - Token mismatch[/red]")
        return False

    return True


@click.command(name="env:list")
@click.option("--all", "show_all", is_flag=True, help="Show all vars (including infra)")
@click.option("--app", help="Filter by app (api, dashboard, services)")
@click.option(
    "--no-mask", is_flag=True, help="Show full values (requires verification)"
)
def env_list(show_all, app, no_mask):
    """
    View environment variables (secure)

    \b
    Examples:
      superdeploy env:list              # App secrets only (masked)
      superdeploy env:list --all        # All vars (masked)
      superdeploy env:list --no-mask    # Full values (requires password)
      superdeploy env:list --app api    # API-specific vars

    \b
    Security:
    - Passwords are masked by default
    - Full values require verification
    - Nothing is stored in history
    """
    env_vars = load_env()

    # Verification for unmasked view
    if no_mask:
        if not verify_password(env_vars):
            raise SystemExit(1)

    # Create table
    table = Table(
        title="Environment Variables", show_header=True, header_style="bold cyan"
    )
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Category", style="dim")

    # Categorize vars
    infra_keys = [
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "SSH_KEY_PATH",
        "SSH_USER",
        "CORE_EXTERNAL_IP",
        "CORE_INTERNAL_IP",
        "SCRAPE_EXTERNAL_IP",
        "SCRAPE_INTERNAL_IP",
        "PROXY_EXTERNAL_IP",
        "PROXY_INTERNAL_IP",
        "FORGEJO_ADMIN_USER",
        "FORGEJO_ADMIN_PASSWORD",
        "FORGEJO_ADMIN_EMAIL",
        "FORGEJO_ORG",
        "FORGEJO_PAT",
        "REPO_SUPERDEPLOY",
        "DOCKER_USERNAME",
        "DOCKER_TOKEN",
        "GITHUB_TOKEN",
        "VM_MACHINE_TYPE",
        "VM_DISK_SIZE",
        "VM_IMAGE",
    ]

    app_keys = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "RABBITMQ_USER",
        "RABBITMQ_PASSWORD",
        "REDIS_PASSWORD",
        "API_SECRET_KEY",
        "GRAFANA_ADMIN_USER",
        "GRAFANA_ADMIN_PASSWORD",
        "ALERT_EMAIL",
        "SENTRY_DSN",
    ]

    # Filter logic
    for key, value in sorted(env_vars.items()):
        # Skip internal keys
        if key in ["ENV_FILE_PATH"]:
            continue

        # Category determination
        if key in infra_keys:
            category = "infra"
        elif key in app_keys:
            category = "app"
        else:
            category = "other"

        # Filter by --all flag
        if not show_all and category == "infra":
            continue

        # Filter by --app flag
        if app:
            app_related = get_addon_prefixes(project)
            if not any(prefix in key for prefix in app_related):
                continue

        # Mask sensitive values
        if no_mask:
            display_value = value
        else:
            sensitive_keywords = ["PASSWORD", "TOKEN", "SECRET", "KEY", "PAT"]
            if any(keyword in key.upper() for keyword in sensitive_keywords):
                if len(value) > 8:
                    display_value = f"{value[:4]}...{value[-4:]}"
                else:
                    display_value = "***"
            else:
                # Truncate long values
                display_value = value[:60] + "..." if len(value) > 60 else value

        # Add row
        table.add_row(key, display_value, category)

    # Print table
    console.print("\n")
    console.print(table)

    # Security notice
    if no_mask:
        console.print(
            "\n[yellow]⚠️  Full values displayed. "
            "Clear your terminal history: [bold]history -c[/bold][/yellow]"
        )
    else:
        console.print(
            "\n[dim]💡 Tip: Use --no-mask to see full values (requires verification)[/dim]"
        )


@click.command(name="env:check")
def env_check():
    """
    Check environment configuration health

    Validates:
    - Required vars are set
    - No placeholder values
    - Secure password strength
    """
    env_vars = load_env()

    console.print(
        Panel("[bold cyan]🔍 Environment Health Check[/bold cyan]", expand=False)
    )

    issues = []
    warnings = []

    # Check required vars
    required = [
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "SSH_KEY_PATH",
        "DOCKER_USERNAME",
        "GITHUB_TOKEN",
        "POSTGRES_PASSWORD",
        "RABBITMQ_PASSWORD",
        "API_SECRET_KEY",
    ]

    for key in required:
        value = env_vars.get(key, "")

        if not value:
            issues.append(f"❌ {key}: Not set")
        elif value in ["your-project-id", "your-token", "your-username"]:
            issues.append(f"❌ {key}: Still has placeholder value")
        elif "PASSWORD" in key or "SECRET" in key or "TOKEN" in key:
            # Check password strength
            if len(value) < 16:
                warnings.append(f"⚠️  {key}: Short password (< 16 chars)")

    # Print results
    if issues:
        console.print("\n[red]Issues found:[/red]")
        for issue in issues:
            console.print(f"  {issue}")

    if warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  {warning}")

    if not issues and not warnings:
        console.print("\n[green]✅ All checks passed! Environment is healthy.[/green]")

    # Summary
    console.print("\n[cyan]Summary:[/cyan]")
    console.print(f"  Total vars: {len(env_vars)}")
    console.print(f"  Issues: {len(issues)}")
    console.print(f"  Warnings: {len(warnings)}")
