"""SuperDeploy CLI - Validate command (Refactored)"""

import click
from dataclasses import dataclass
from typing import List, Dict, Any
from rich.table import Table

from cli.base import BaseCommand, ProjectCommand
from cli.secret_manager import SecretManager


@dataclass
class ValidationResult:
    """Results from validation checks."""

    errors: List[str]
    warnings: List[str]

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return not self.has_errors


class ValidateProjectCommand(ProjectCommand):
    """Validate project configuration."""

    def execute(self) -> None:
        """Execute project validation."""
        self.show_header(
            title="Validate Project Configuration",
            project=self.project_name,
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, "validate")

        logger.step("Running validation checks")
        self.console.print("\n[bold]Running validation checks...[/bold]\n")

        # Run all validations
        result = self._run_validations()

        logger.success("Validation checks complete")

        # Display results
        self._display_results(result, logger)

    def _run_validations(self) -> ValidationResult:
        """Run all validation checks."""
        errors = []
        warnings = []

        config = self.config_service.get_raw_config(self.project_name)

        # Run individual validation checks
        errors.extend(self._validate_required_fields(config))
        errors.extend(self._validate_apps(config, warnings))
        errors.extend(self._validate_port_conflicts(config))
        self._validate_vms(config, warnings)
        self._validate_addons(config)
        self._validate_github(config, warnings)
        self._validate_network(config, warnings)
        errors.extend(self._validate_secrets(warnings))

        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_required_fields(self, config: Dict[str, Any]) -> List[str]:
        """Validate required configuration fields."""
        errors = []
        required_fields = ["project", "apps", "addons", "github", "vms"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
            else:
                self.console.print(f"[green]✓[/green] Required field: {field}")

        return errors

    def _validate_apps(self, config: Dict[str, Any], warnings: List[str]) -> List[str]:
        """Validate app configurations."""
        errors = []

        if "apps" in config:
            apps = config["apps"]
            if not apps or len(apps) == 0:
                errors.append("No apps defined")
            else:
                self.console.print(f"[green]✓[/green] Apps defined: {len(apps)}")

                # Check each app
                for app_name, app_config in apps.items():
                    if "port" not in app_config:
                        warnings.append(f"App '{app_name}' has no port defined")
                    if "vm" not in app_config:
                        warnings.append(f"App '{app_name}' has no VM assignment")

        return errors

    def _validate_port_conflicts(self, config: Dict[str, Any]) -> List[str]:
        """Validate port assignments for conflicts."""
        errors = []
        if "apps" in config:
            used_ports = []
            for app_name, app_config in config["apps"].items():
                if "port" in app_config:
                    port = app_config["port"]
                    if port in used_ports:
                        errors.append(f"Port conflict: {port} used by multiple apps")
                    used_ports.append(port)

            self.console.print(
                f"[green]✓[/green] Port assignments: {len(used_ports)} ports"
            )

        return errors

    def _validate_vms(self, config: Dict[str, Any], warnings: List[str]) -> None:
        """Validate VM configurations."""
        if "vms" in config:
            vms = config["vms"]
            self.console.print(f"[green]✓[/green] VMs defined: {len(vms)}")

            # Validate VM services
            for vm_name, vm_config in vms.items():
                if "services" in vm_config:
                    for service in vm_config["services"]:
                        if "addons" in config and service not in config["addons"]:
                            warnings.append(
                                f"VM '{vm_name}' uses service '{service}' but it's not in addons"
                            )

    def _validate_addons(self, config: Dict[str, Any]) -> None:
        """Validate addon configurations."""
        if "addons" in config:
            self.console.print(
                f"[green]✓[/green] Addons configured: {len(config['addons'])}"
            )

    def _validate_github(self, config: Dict[str, Any], warnings: List[str]) -> None:
        """Validate GitHub configuration."""
        if "github" in config:
            if "organization" in config["github"]:
                self.console.print(
                    f"[green]✓[/green] GitHub organization: {config['github']['organization']}"
                )
            else:
                warnings.append("GitHub organization not configured")

    def _validate_network(self, config: Dict[str, Any], warnings: List[str]) -> None:
        """Validate network configuration."""
        if "network" in config:
            if "vpc_subnet" in config["network"]:
                self.console.print(
                    f"[green]✓[/green] VPC subnet: {config['network']['vpc_subnet']}"
                )
            if "docker_subnet" in config["network"]:
                self.console.print(
                    f"[green]✓[/green] Docker subnet: {config['network']['docker_subnet']}"
                )
        else:
            warnings.append("Network configuration not found")

    def _validate_secrets(self, warnings: List[str]) -> List[str]:
        """Validate secrets configuration."""
        errors = []

        secret_mgr = SecretManager(self.project_root, self.project_name)
        secrets_data = secret_mgr.load_secrets()

        if secrets_data:
            shared_secrets = secrets_data.shared.values

            # Check Docker credentials (required for deployment)
            docker_username = shared_secrets.get("DOCKER_USERNAME", "")
            docker_token = shared_secrets.get("DOCKER_TOKEN", "")

            if not docker_username or not docker_token:
                errors.append(
                    "Missing Docker credentials in secrets.yml (DOCKER_USERNAME and DOCKER_TOKEN required for deployment)"
                )
                self.console.print("[red]✗[/red] Docker credentials: Missing")
            else:
                self.console.print("[green]✓[/green] Docker credentials: Configured")

            # Check ORCHESTRATOR_IP (should be filled after orchestrator:up)
            orchestrator_ip = shared_secrets.get("ORCHESTRATOR_IP", "")
            if not orchestrator_ip:
                warnings.append(
                    "ORCHESTRATOR_IP not set (run 'superdeploy orchestrator:up' first)"
                )
            else:
                self.console.print(
                    f"[green]✓[/green] Orchestrator IP: {orchestrator_ip}"
                )

            # Check SMTP credentials (optional, but warn if missing)
            smtp_host = shared_secrets.get("SMTP_HOST", "")
            smtp_password = shared_secrets.get("SMTP_PASSWORD", "")

            if not smtp_host or not smtp_password:
                warnings.append(
                    "SMTP credentials not configured (email notifications will not work)"
                )
                self.console.print(
                    "[yellow]⚠[/yellow] SMTP credentials: Not configured"
                )
            else:
                self.console.print("[green]✓[/green] SMTP credentials: Configured")
        else:
            errors.append("secrets.yml not found or invalid")

        return errors

    def _display_results(self, result: ValidationResult, logger) -> None:
        """Display validation results."""
        config = self.config_service.get_raw_config(self.project_name)

        self.console.print("\n[bold]Validation Results:[/bold]\n")

        if result.has_errors:
            logger.log_error(f"Validation failed with {len(result.errors)} error(s)")
            self.console.print("[bold red]❌ Errors:[/bold red]")
            for error in result.errors:
                self.console.print(f"  • {error}")
            self.console.print()

        if result.has_warnings:
            logger.warning(f"Validation has {len(result.warnings)} warning(s)")
            self.console.print("[bold yellow]⚠️  Warnings:[/bold yellow]")
            for warning in result.warnings:
                self.console.print(f"  • {warning}")
            self.console.print()

        if result.is_valid and not result.has_warnings:
            logger.success("Configuration is valid")
            self.console.print("[color(248)]Configuration is valid.[/color(248)]")

            # Display summary table
            table = Table(
                title="Configuration Summary", title_justify="left", padding=(0, 1)
            )
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            # Project info
            project_name = (
                config.get("project", {}).get("name", "N/A")
                if isinstance(config.get("project"), dict)
                else config.get("project", "N/A")
            )
            table.add_row("Project", project_name)
            table.add_row("Apps", str(len(config.get("apps", {}))))
            table.add_row("VMs", str(len(config.get("vms", {}))))
            table.add_row("Addons", str(len(config.get("addons", {}))))

            # GitHub org
            github_org = config.get("github", {}).get("organization", "N/A")
            table.add_row("GitHub Org", github_org)

            self.console.print()
            self.console.print(table)
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

            raise SystemExit(0)
        elif result.has_errors:
            self.console.print("[bold red]❌ Validation failed with errors[/bold red]")
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(1)
        else:
            self.console.print(
                "[bold yellow]⚠️  Validation passed with warnings[/bold yellow]"
            )
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(0)


class ValidateAddonsCommand(BaseCommand):
    """Validate addon structure and configuration."""

    def __init__(
        self,
        project: str = None,
        addon: str = None,
        fix: bool = False,
        verbose: bool = False,
    ):
        super().__init__(verbose=verbose)
        self.project_name = project
        self.addon_name = addon
        self.fix = fix

    def execute(self) -> None:
        """Execute addon validation."""
        self.show_header(
            title="Validate Addons",
            details={"Target": self.addon_name if self.addon_name else "All addons"},
        )

        # Initialize logger
        logger = self.init_logger("addons", "validate")

        if self.fix:
            self.console.print("[yellow]⚠️  Auto-fix is not yet implemented[/yellow]\n")

        logger.step("Starting addon validation")

        from cli.core.addon_validator import AddonValidator

        # Get addons path
        addons_path = self.project_root / "addons"

        # Initialize validator
        validator = AddonValidator(addons_path)

        # Validate addon(s)
        if self.addon_name:
            results = [validator.validate_addon(self.addon_name)]
        elif self.project_name:
            # Load project config
            from cli.services import ConfigService

            try:
                config_service = ConfigService(self.project_root)
                project_config = config_service.load_project_config(self.project_name)
                enabled_addons = list(project_config.get_addons().keys())

                if not enabled_addons:
                    self.console.print(
                        f"[yellow]⚠️  No addons enabled for project '{self.project_name}'[/yellow]"
                    )
                    raise SystemExit(0)

                self.console.print(
                    f"[dim]Validating {len(enabled_addons)} addons for project '{self.project_name}'...[/dim]\n"
                )
                results = [validator.validate_addon(a) for a in enabled_addons]
            except Exception as e:
                self.console.print(f"[red]❌ Error loading project: {e}[/red]")
                raise SystemExit(1)
        else:
            results = validator.validate_all_addons()

        if not results:
            self.console.print("[yellow]⚠️  No addons found to validate[/yellow]")
            raise SystemExit(0)

        # Display results
        total_passed = 0
        total_failed = 0

        for result in results:
            # Create status indicator
            if result.passed:
                status = "[green]✓ PASS[/green]"
                total_passed += 1
            else:
                status = "[red]✗ FAIL[/red]"
                total_failed += 1

            # Display addon header
            self.console.print(f"\n{status} [bold]{result.addon_name}[/bold]")

            if result.error_count > 0:
                self.console.print(f"  [red]Errors: {result.error_count}[/red]")
            if result.warning_count > 0:
                self.console.print(
                    f"  [yellow]Warnings: {result.warning_count}[/yellow]"
                )

            # Display checks
            for check in result.checks:
                if check.severity == "info" and check.passed:
                    continue  # Skip passed info checks

                # Color based on severity
                if check.passed:
                    icon = "✓"
                    color = "green"
                else:
                    icon = "✗"
                    if check.severity == "error":
                        color = "red"
                    elif check.severity == "warning":
                        color = "yellow"
                    else:
                        color = "dim"

                self.console.print(f"    [{color}]{icon}[/{color}] {check.message}")

                # Show fix suggestion
                if not check.passed and check.fix_suggestion:
                    self.console.print(f"      [dim]→ {check.fix_suggestion}[/dim]")

        # Summary
        self.console.print("\n" + "─" * 50)
        self.console.print("\n[bold]Summary:[/bold]")
        self.console.print(f"  Total addons: {len(results)}")
        self.console.print(f"  [green]Passed: {total_passed}[/green]")
        self.console.print(f"  [red]Failed: {total_failed}[/red]")

        # Failed addons table
        if total_failed > 0:
            self.console.print("\n[bold red]Failed Addons:[/bold red]")

            table = Table(
                title="Addon Validation Results", title_justify="left", padding=(0, 1)
            )
            table.add_column("Addon", style="cyan")
            table.add_column("Errors", style="red")
            table.add_column("Warnings", style="yellow")

            for result in results:
                if not result.passed:
                    table.add_row(
                        result.addon_name,
                        str(result.error_count),
                        str(result.warning_count),
                    )

            self.console.print(table)

        # Exit code
        if total_failed > 0:
            logger.log_error(f"Validation failed: {total_failed} addon(s) failed")
            self.console.print("\n[bold red]❌ Validation failed[/bold red]")
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(1)
        else:
            logger.success(f"All {total_passed} addon(s) validated successfully")
            self.console.print(
                "\n[color(248)]All addons validated successfully.[/color(248)]"
            )
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(0)


@click.command(name="validate:project")
def validate_project(project):
    """
    Validate project configuration

    \b
    Examples:
      superdeploy acme:validate

    \b
    This command validates:
    - config.yml structure and required fields
    - Port assignments (no conflicts)
    - Service definitions
    - Repository URLs
    - Network configuration
    """
    cmd = ValidateProjectCommand(project, verbose=False)
    cmd.run()


@click.command(name="validate:addons")
@click.option("--addon", "-a", help="Validate specific addon")
@click.option(
    "--fix", is_flag=True, help="Attempt to auto-fix issues (not implemented yet)"
)
def validate_addons(project=None, addon=None, fix=False):
    """
    Validate addon structure and configuration

    \b
    Examples:
      superdeploy validate:addons                    # Validate all addons
      superdeploy validate:addons -a postgres        # Validate specific addon
      superdeploy cheapa:validate:addons             # Validate addons for project
      superdeploy validate:addons --fix              # Auto-fix issues (future)

    \b
    This command validates:
    - Required files (addon.yml, docker-compose.yml.j2)
    - Metadata fields (name, description, version, category)
    - Compose template structure
    - Healthcheck configuration
    - Ansible tasks (anti-patterns)
    """
    cmd = ValidateAddonsCommand(project, addon, fix, verbose=False)
    cmd.run()
