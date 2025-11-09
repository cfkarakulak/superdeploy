"""SuperDeploy CLI - Secure env viewing command"""

import click
import getpass
from rich.table import Table
from rich.panel import Panel
from cli.base import BaseCommand


def get_addon_prefixes(project, project_root):
    """
    Get environment variable prefixes from addon metadata.

    Args:
        project (str): Project name
        project_root: Path to project root

    Returns:
        list: List of environment variable prefixes
    """
    from cli.core.addon_loader import AddonLoader

    try:
        addons_dir = project_root / "addons"
        addon_loader = AddonLoader(addons_dir)

        # Load project config to get enabled addons
        from cli.services.config_service import ConfigService

        config_service = ConfigService(project_root)
        project_config = config_service.load_project_config(project)

        # Load addons
        addons = addon_loader.load_addons_for_project(project_config.raw_config)

        # Extract prefixes from env var names
        prefixes = set()
        for addon_name, addon in addons.items():
            for var_name in addon.get_env_var_names():
                # Extract prefix (e.g., "POSTGRES_HOST" -> "POSTGRES")
                prefix = var_name.split("_")[0]
                prefixes.add(prefix)

        # Only addon prefixes - no hardcoded app-specific prefixes
        return list(prefixes)
    except Exception:
        # Fallback to common addon prefixes if loading fails
        return ["POSTGRES", "RABBITMQ", "REDIS", "MONGODB", "ELASTICSEARCH"]


def verify_password(env_vars, console):
    """Verify user identity with password challenge"""
    # Use GITHUB_TOKEN as verification (secure and already in secrets.yml)
    expected_token = env_vars.get("GITHUB_TOKEN", "")

    if not expected_token or expected_token in ["", "your-github-token"]:
        console.print("[red]❌ GITHUB_TOKEN not configured in secrets.yml[/red]")
        console.print("[yellow]Set a valid GITHUB_TOKEN to use --no-mask[/yellow]")
        return False

    console.print(
        Panel(
            "[yellow]⚠️  Sensitive data access[/yellow]\n\n"
            "[white]Enter your GITHUB_TOKEN (from secrets.yml):[/white]",
            border_style="yellow",
        )
    )

    password = getpass.getpass("Token: ")

    # Verify token matches
    if password.strip() != expected_token.strip():
        console.print("[red]❌ Access denied - Token mismatch[/red]")
        return False

    return True


class EnvListCommand(BaseCommand):
    """View environment variables (secure)."""

    def __init__(
        self,
        show_all: bool = False,
        app: str = None,
        no_mask: bool = False,
        verbose: bool = False,
    ):
        super().__init__(verbose=verbose)
        self.show_all = show_all
        self.app = app
        self.no_mask = no_mask

    def execute(self) -> None:
        """Execute env:list command."""
        self.show_header(
            title="Environment Variables",
            details={
                "Scope": "All" if self.show_all else "App secrets only",
                "App": self.app if self.app else "All apps",
                "Masked": "No" if self.no_mask else "Yes",
            },
        )

        # Load from orchestrator secrets.yml (shared secrets)
        # This command is for global env, not project-specific
        from cli.secret_manager import SecretManager

        # Get first project or use default
        projects_dir = self.project_root / "projects"
        projects = [p.name for p in projects_dir.iterdir() if p.is_dir()]
        if not projects:
            self.console.print("[red]❌ No projects found[/red]")
            raise SystemExit(1)
        secret_mgr = SecretManager(self.project_root, projects[0])
        secrets_data = secret_mgr.load_secrets()
        env_vars = secrets_data.get("secrets", {}).get("shared", {})

        # Verification for unmasked view
        if self.no_mask:
            if not verify_password(env_vars, self.console):
                raise SystemExit(1)

        # Create table
        table = Table(
            title="Environment Variables",
            show_header=True,
            header_style="bold cyan",
            title_justify="left",
            padding=(0, 1),
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
        ]

        # Filter logic
        for key, value in sorted(env_vars.items()):
            # Category determination
            if key in infra_keys:
                category = "infra"
            elif key in app_keys:
                category = "app"
            else:
                category = "other"

            # Filter by --all flag
            if not self.show_all and category == "infra":
                continue

            # Filter by --app flag
            if self.app:
                app_related = get_addon_prefixes(projects[0], self.project_root)
                if not any(prefix in key for prefix in app_related):
                    continue

            # Mask sensitive values
            if self.no_mask:
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
        self.console.print("\n")
        self.console.print(table)

        # Security notice
        if self.no_mask:
            self.console.print(
                "\n[yellow]⚠️  Full values displayed. "
                "Clear your terminal history: [bold]history -c[/bold][/yellow]"
            )
        else:
            self.console.print(
                "\n[dim]💡 Tip: Use --no-mask to see full values (requires verification)[/dim]"
            )


class EnvCheckCommand(BaseCommand):
    """Check environment configuration health."""

    def execute(self) -> None:
        """Execute env:check command."""
        self.show_header(
            title="Environment Health Check",
            subtitle="Validating configuration and security",
        )

        # Load from orchestrator secrets.yml (shared secrets)
        from cli.secret_manager import SecretManager

        # Get first project or use default
        projects_dir = self.project_root / "projects"
        projects = [p.name for p in projects_dir.iterdir() if p.is_dir()]
        if not projects:
            self.console.print("[red]❌ No projects found[/red]")
            raise SystemExit(1)
        secret_mgr = SecretManager(self.project_root, projects[0])
        secrets_data = secret_mgr.load_secrets()
        env_vars = secrets_data.get("secrets", {}).get("shared", {})

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
            self.console.print("\n[red]Issues found:[/red]")
            for issue in issues:
                self.console.print(f"  {issue}")

        if warnings:
            self.console.print("\n[yellow]Warnings:[/yellow]")
            for warning in warnings:
                self.console.print(f"  {warning}")

        if not issues and not warnings:
            self.console.print(
                "\n[green]✅ All checks passed! Environment is healthy.[/green]"
            )

        # Summary
        self.console.print("\n[cyan]Summary:[/cyan]")
        self.console.print(f"  Total vars: {len(env_vars)}")
        self.console.print(f"  Issues: {len(issues)}")
        self.console.print(f"  Warnings: {len(warnings)}")


@click.command(name="env:list")
@click.option("--all", "show_all", is_flag=True, help="Show all vars (including infra)")
@click.option("--app", help="Filter by app (api, dashboard, services)")
@click.option(
    "--no-mask", is_flag=True, help="Show full values (requires verification)"
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def env_list(show_all, app, no_mask, verbose):
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
    cmd = EnvListCommand(show_all=show_all, app=app, no_mask=no_mask, verbose=verbose)
    cmd.run()


@click.command(name="env:check")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def env_check(verbose):
    """
    Check environment configuration health

    Validates:
    - Required vars are set
    - No placeholder values
    - Secure password strength
    """
    cmd = EnvCheckCommand(verbose=verbose)
    cmd.run()
