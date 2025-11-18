"""SuperDeploy CLI - Secure env viewing command"""

import click
import getpass
from dataclasses import dataclass
from typing import Dict, List, Set
from rich.table import Table
from rich.panel import Panel

from cli.base import BaseCommand
from cli.secret_manager import SecretManager


@dataclass
class EnvCategorization:
    """Environment variable categorization."""

    infra_keys: Set[str]
    app_keys: Set[str]

    def get_category(self, key: str) -> str:
        """Get category for a given key."""
        if key in self.infra_keys:
            return "infra"
        elif key in self.app_keys:
            return "app"
        else:
            return "other"


class EnvVarHelper:
    """Helper class for environment variable operations."""

    # Default categorization
    DEFAULT_INFRA_KEYS = {
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
        "REPOSITORY_TOKEN",
        "VM_MACHINE_TYPE",
        "VM_DISK_SIZE",
        "VM_IMAGE",
    }

    DEFAULT_APP_KEYS = {
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
    }

    SENSITIVE_KEYWORDS = {"PASSWORD", "TOKEN", "SECRET", "KEY", "PAT"}

    @classmethod
    def get_addon_prefixes(cls, project: str, project_root) -> List[str]:
        """Get environment variable prefixes from addon metadata."""
        from cli.core.addon_loader import AddonLoader
        from cli.services.config_service import ConfigService

        try:
            addons_dir = project_root / "addons"
            addon_loader = AddonLoader(addons_dir)
            config_service = ConfigService(project_root)
            project_config = config_service.load_project_config(project)
            addons = addon_loader.load_addons_for_project(project_config.raw_config)

            # Extract prefixes from env var names
            prefixes = set()
            for addon_name, addon in addons.items():
                for var_name in addon.get_env_var_names():
                    prefix = var_name.split("_")[0]
                    prefixes.add(prefix)

            return list(prefixes)
        except Exception:
            # Fallback to common addon prefixes
            return ["POSTGRES", "RABBITMQ", "REDIS", "MONGODB", "ELASTICSEARCH"]

    @classmethod
    def mask_value(cls, key: str, value: str) -> str:
        """Mask a sensitive value."""
        if any(keyword in key.upper() for keyword in cls.SENSITIVE_KEYWORDS):
            if len(value) > 8:
                return f"{value[:4]}...{value[-4:]}"
            else:
                return "***"
        else:
            # Truncate long values
            return value[:60] + "..." if len(value) > 60 else value

    @classmethod
    def verify_password(cls, env_vars: Dict[str, str], console) -> bool:
        """Verify user identity with password challenge."""
        expected_token = env_vars.get("REPOSITORY_TOKEN", "")

        if not expected_token or expected_token in ["", "your-github-token"]:
            console.print("[red]❌ REPOSITORY_TOKEN not configured in database[/red]")
            console.print(
                "[yellow]Set a valid REPOSITORY_TOKEN to use --no-mask[/yellow]"
            )
            return False

        console.print(
            Panel(
                "[yellow]⚠️  Sensitive data access[/yellow]\n\n"
                "[white]Enter your REPOSITORY_TOKEN (from database):[/white]",
                border_style="yellow",
            )
        )

        password = getpass.getpass("Token: ")

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
        json_output: bool = False,
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.show_all = show_all
        self.app = app
        self.no_mask = no_mask

    def execute(self) -> None:
        """Execute env:list command."""
        # Get first project
        projects = self._get_projects()
        env_vars = self._load_env_vars(projects[0])

        # Verification for unmasked view
        if self.no_mask:
            if not self.json_output and not EnvVarHelper.verify_password(
                env_vars, self.console
            ):
                raise SystemExit(1)

        # JSON output mode
        if self.json_output:
            masked_vars = {}
            for key, value in env_vars.items():
                value_str = str(value)
                # Mask sensitive values unless no_mask is True
                if not self.no_mask and any(
                    sensitive in key.upper()
                    for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY", "PAT"]
                ):
                    masked_vars[key] = (
                        "***" + value_str[-4:] if len(value_str) > 4 else "***"
                    )
                else:
                    masked_vars[key] = value_str

            self.output_json(
                {
                    "project": projects[0],
                    "variables": masked_vars,
                    "total": len(masked_vars),
                    "masked": not self.no_mask,
                }
            )
            return

        self.show_header(
            title="Environment Variables",
            details={
                "Scope": "All" if self.show_all else "App secrets only",
                "App": self.app if self.app else "All apps",
                "Masked": "No" if self.no_mask else "Yes",
            },
        )

        # Build and display table
        table = self._build_table(env_vars, projects[0])
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

    def _get_projects(self) -> List[str]:
        """Get list of projects."""
        projects_dir = self.project_root / "projects"
        projects = [p.name for p in projects_dir.iterdir() if p.is_dir()]
        if not projects:
            self.console.print("[red]❌ No projects found[/red]")
            raise SystemExit(1)
        return projects

    def _load_env_vars(self, project_name: str) -> Dict[str, str]:
        """Load environment variables from secrets."""
        secret_mgr = SecretManager(self.project_root, project_name)
        secrets_config = secret_mgr.load_secrets()
        # Convert SharedSecrets object to dict
        env_vars = {}
        if hasattr(secrets_config.shared, "__dict__"):
            for key, value in secrets_config.shared.__dict__.items():
                if value is not None:
                    env_vars[key] = value
        return env_vars

    def _build_table(self, env_vars: Dict[str, str], project_name: str) -> Table:
        """Build environment variables table."""
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

        # Create categorization
        categorization = EnvCategorization(
            infra_keys=EnvVarHelper.DEFAULT_INFRA_KEYS,
            app_keys=EnvVarHelper.DEFAULT_APP_KEYS,
        )

        # Filter and add rows
        for key, value in sorted(env_vars.items()):
            value = str(value)
            category = categorization.get_category(key)

            # Filter by --all flag
            if not self.show_all and category == "infra":
                continue

            # Filter by --app flag
            if self.app:
                app_related = EnvVarHelper.get_addon_prefixes(
                    project_name, self.project_root
                )
                if not any(prefix in key for prefix in app_related):
                    continue

            # Mask or display value
            display_value = (
                value if self.no_mask else EnvVarHelper.mask_value(key, value)
            )

            table.add_row(key, display_value, category)

        return table


class EnvCheckCommand(BaseCommand):
    """Check environment configuration health."""

    # Required environment variables
    REQUIRED_VARS = [
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "SSH_KEY_PATH",
        "DOCKER_USERNAME",
        "REPOSITORY_TOKEN",
        "POSTGRES_PASSWORD",
        "RABBITMQ_PASSWORD",
        "API_SECRET_KEY",
    ]

    # Placeholder values to detect
    PLACEHOLDER_VALUES = {"your-project-id", "your-token", "your-username"}

    def execute(self) -> None:
        """Execute env:check command."""
        # Load environment variables
        projects = self._get_projects()
        env_vars = self._load_env_vars(projects[0])

        # Run checks
        issues, warnings = self._check_environment(env_vars)

        # JSON output mode
        if self.json_output:
            self.output_json(
                {
                    "project": projects[0],
                    "total_vars": len(env_vars),
                    "issues": issues,
                    "warnings": warnings,
                    "issue_count": len(issues),
                    "warning_count": len(warnings),
                    "status": "failed"
                    if issues
                    else ("warning" if warnings else "passed"),
                }
            )
            return

        self.show_header(
            title="Environment Health Check",
            subtitle="Validating configuration and security",
        )

        # Display results
        self._display_results(issues, warnings, len(env_vars))

    def _get_projects(self) -> List[str]:
        """Get list of projects."""
        projects_dir = self.project_root / "projects"
        projects = [p.name for p in projects_dir.iterdir() if p.is_dir()]
        if not projects:
            self.console.print("[red]❌ No projects found[/red]")
            raise SystemExit(1)
        return projects

    def _load_env_vars(self, project_name: str) -> Dict[str, str]:
        """Load environment variables from secrets."""
        secret_mgr = SecretManager(self.project_root, project_name)
        secrets_config = secret_mgr.load_secrets()
        # Convert SharedSecrets object to dict
        env_vars = {}
        if hasattr(secrets_config.shared, "__dict__"):
            for key, value in secrets_config.shared.__dict__.items():
                if value is not None:
                    env_vars[key] = value
        return env_vars

    def _check_environment(
        self, env_vars: Dict[str, str]
    ) -> tuple[List[str], List[str]]:
        """Check environment variables for issues."""
        issues = []
        warnings = []

        for key in self.REQUIRED_VARS:
            value = str(env_vars.get(key, ""))

            if not value:
                issues.append(f"❌ {key}: Not set")
            elif value in self.PLACEHOLDER_VALUES:
                issues.append(f"❌ {key}: Still has placeholder value")
            elif any(kw in key for kw in ["PASSWORD", "SECRET", "TOKEN"]):
                # Check password strength
                if len(value) < 16:
                    warnings.append(f"⚠️  {key}: Short password (< 16 chars)")

        return issues, warnings

    def _display_results(
        self, issues: List[str], warnings: List[str], total_vars: int
    ) -> None:
        """Display check results."""
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
        self.console.print(f"  Total vars: {total_vars}")
        self.console.print(f"  Issues: {len(issues)}")
        self.console.print(f"  Warnings: {len(warnings)}")


@click.command(name="env:list")
@click.option("--all", "show_all", is_flag=True, help="Show all vars (including infra)")
@click.option("--app", help="Filter by app (api, dashboard, services)")
@click.option(
    "--no-mask", is_flag=True, help="Show full values (requires verification)"
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def env_list(
    project=None,
    show_all=False,
    app=None,
    no_mask=False,
    verbose=False,
    json_output=False,
):
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
    cmd = EnvListCommand(
        show_all=show_all,
        app=app,
        no_mask=no_mask,
        verbose=verbose,
        json_output=json_output,
    )
    cmd.run()


@click.command(name="env:check")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def env_check(project=None, verbose=False, json_output=False):
    """
    Check environment configuration health

    Validates:
    - Required vars are set
    - No placeholder values
    - Secure password strength
    """
    cmd = EnvCheckCommand(verbose=verbose, json_output=json_output)
    cmd.run()
