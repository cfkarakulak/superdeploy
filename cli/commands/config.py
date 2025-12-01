"""SuperDeploy CLI - Config command"""

import click
import subprocess
import yaml
from pathlib import Path
from rich.table import Table
from cli.base import ProjectCommand
from cli.terraform_utils import get_terraform_outputs


class ConfigSetCommand(ProjectCommand):
    """Set configuration variable (Heroku-like!)."""

    def __init__(
        self,
        project_name: str,
        key_value: str,
        app: str = None,
        environment: str = "production",
        deploy: bool = False,
        no_sync: bool = False,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.key_value = key_value
        self.app = app
        self.environment = environment
        self.deploy = deploy
        self.no_sync = no_sync

    def execute(self) -> None:
        """Execute config:set command - Database-backed."""
        from cli.logger import DeployLogger
        from cli.secret_manager import SecretManager

        # Parse key=value
        try:
            key, value = self.key_value.split("=", 1)
        except ValueError:
            self.exit_with_error("Invalid format! Use: KEY=VALUE")

        self.show_header(
            title="Set Configuration",
            subtitle="Heroku-like config management (Database)",
            project=self.project_name,
        )

        logger = DeployLogger(self.project_name, "config-set", verbose=False)

        # Step 1: Update database
        if logger:
            logger.step("[1/4] Updating Database")

        secret_mgr = SecretManager(
            self.project_root, self.project_name, self.environment
        )

        try:
            # Set secret in database
            if self.app:
                # App-specific secret
                secret_mgr.set_app_secret(self.app, key, value)
                location = f"app:{self.app}"
            else:
                # Shared secret (all apps)
                secret_mgr.set_shared_secret(key, value)
                location = "shared"

            if logger:
                logger.log(f"✓ Updated {key} in {location}")

        except Exception as e:
            if logger:
                logger.log_error(f"Failed to update secret: {e}")
            self.exit_with_error(str(e))

        # Step 2: Sync to GitHub
        if not self.no_sync:
            if logger:
                logger.step("[2/4] Syncing to GitHub")
            if logger:
                logger.log(
                    f"Running sync command for {self.environment} environment..."
                )

            try:
                import sys

                sync_cmd = [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"{self.project_name}:sync",
                    "-e",
                    self.environment,
                ]

                result = subprocess.run(
                    sync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0:
                    if logger:
                        logger.log(f"✓ Synced to GitHub ({self.environment})")
                else:
                    if logger:
                        logger.warning("⚠ Sync had issues")
                    if result.stderr:
                        for line in result.stderr.split("\n")[:3]:
                            if line.strip():
                                if logger:
                                    logger.warning(f"  {line}")
            except subprocess.TimeoutExpired:
                if logger:
                    logger.warning("⚠ Sync timed out")
            except Exception as e:
                if logger:
                    logger.log_error(f"Sync failed: {e}")
                if logger:
                    logger.warning("Continuing without sync...")
        else:
            if logger:
                logger.step("[2/4] Skipping Sync")
            if logger:
                logger.log("--no-sync flag provided")

        # Step 3: Trigger Deployment
        if self.deploy:
            if logger:
                logger.step("[3/4] Triggering Deployment")

            # Load project config
            project_config_file = (
                self.project_root / "projects" / self.project_name / "config.yml"
            )
            with open(project_config_file) as f:
                config = yaml.safe_load(f)

            apps = config.get("apps", {})

            # Filter apps if -a specified
            if self.app:
                if self.app not in apps:
                    if logger:
                        logger.log_error(
                            f"App '{self.app}' not found in project config"
                        )
                    raise SystemExit(1)
                apps = {self.app: apps[self.app]}

            # Deploy each app
            deployed_count = 0
            failed_count = 0

            for app_name, app_config in apps.items():
                app_path = Path(app_config.get("path", ""))

                if not app_path.exists():
                    if logger:
                        logger.warning(f"⚠ {app_name}: path not found ({app_path})")
                    failed_count += 1
                    continue

                if logger:
                    logger.log(f"Deploying {app_name}...")

                try:
                    # Empty commit to trigger deployment
                    subprocess.run(
                        [
                            "git",
                            "commit",
                            "--allow-empty",
                            "-m",
                            f"config: update {key}",
                        ],
                        cwd=app_path,
                        capture_output=True,
                        text=True,
                    )

                    # Push to production
                    subprocess.run(
                        ["git", "push", "origin", self.environment],
                        cwd=app_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    if logger:
                        logger.log(f"  ✓ {app_name} deployment triggered")
                    deployed_count += 1

                except subprocess.CalledProcessError as e:
                    if logger:
                        logger.log_error(
                            f"  ✗ {app_name} deployment failed: {e.stderr}"
                        )
                    failed_count += 1

            if logger:
                logger.log("")
            if logger:
                logger.log(
                    f"Deployment summary: {deployed_count} succeeded, {failed_count} failed"
                )

            if deployed_count > 0:
                if logger:
                    logger.step("[4/4] Deployment In Progress")
                if logger:
                    logger.log("✓ Deployment triggered via git push")
                if logger:
                    logger.log(
                        f"Watch logs: superdeploy {self.project_name}:logs --follow"
                    )

        else:
            if logger:
                logger.step("[3/4] Skipping Deployment")
            if logger:
                logger.log("Run with --deploy to auto-deploy")
            if logger:
                logger.log(
                    f"Or manually: cd <app-path> && git push origin {self.environment}"
                )

        # Summary
        self.console.print()
        self.console.print("[bold green]✅ Configuration Updated![/bold green]")
        self.console.print()
        self.console.print(f"  [cyan]{key}[/cyan] = [green]{value}[/green]")
        self.console.print()

        if self.deploy:
            self.console.print(
                f"[dim]💡 Tip: Check deployment status with 'superdeploy {self.project_name}:status'[/dim]"
            )
        else:
            self.console.print(
                "[dim]💡 Tip: Run with --deploy to trigger deployment automatically[/dim]"
            )


class ConfigGetCommand(ProjectCommand):
    """Get configuration variable (Heroku-like!)."""

    def __init__(
        self,
        project_name: str,
        key: str,
        app: str = None,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.key = key
        self.app = app

    def execute(self) -> None:
        """Execute config:get command."""
        from cli.secret_manager import SecretManager

        self.show_header(
            title="Get Configuration",
            project=self.project_name,
            details={"Key": self.key, "App": self.app if self.app else "shared"},
        )

        secret_mgr = SecretManager(self.project_root, self.project_name)
        secrets_data = secret_mgr.load_secrets()

        # Get value from appropriate location
        if self.app:
            # Get from app-specific secrets
            app_secrets = secret_mgr.get_app_secrets(self.app)
            value = app_secrets.get(self.key)
            location = f"secrets.{self.app} (merged with shared)"
        else:
            # Get from shared secrets only
            shared_secrets = secrets_data.get("secrets", {}).get("shared", {})
            value = shared_secrets.get(self.key)
            location = "secrets.shared"

        if value:
            # Mask sensitive values
            if any(
                sensitive in self.key.upper()
                for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY"]
            ):
                masked = "***" + str(value)[-4:] if len(str(value)) > 4 else "***"
                self.console.print(
                    f"[cyan]{self.key}[/cyan]=[yellow]{masked}[/yellow] [dim](masked, from {location})[/dim]"
                )
            else:
                self.console.print(
                    f"[cyan]{self.key}[/cyan]=[green]{value}[/green] [dim](from {location})[/dim]"
                )
        else:
            self.console.print(
                f"[yellow]⚠️  {self.key} not found in {location}[/yellow]"
            )
            raise SystemExit(1)


class ConfigListCommand(ProjectCommand):
    """List all configuration variables - Database-backed."""

    def __init__(
        self,
        project_name: str,
        filter_prefix: str = None,
        app: str = None,
        environment: str = "production",
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.filter_prefix = filter_prefix
        self.app = app
        self.environment = environment

    def execute(self) -> None:
        """Execute config:list command."""
        from cli.secret_manager import SecretManager

        secret_mgr = SecretManager(
            self.project_root, self.project_name, self.environment
        )

        # Get appropriate secrets (DB-based system)
        if self.app:
            # Get merged secrets for app
            env_vars = secret_mgr.get_app_secrets(self.app)
            scope = f"{self.app} (shared + app-specific)"
        else:
            # Get only shared secrets from DB
            secrets_data = secret_mgr.load_secrets()
            env_vars = secrets_data.get("shared", {})
            scope = "shared"

        # Filter if specified
        if self.filter_prefix:
            filtered = {
                k: v
                for k, v in env_vars.items()
                if k.upper().startswith(self.filter_prefix.upper())
            }
        else:
            filtered = env_vars

        # JSON output mode
        if self.json_output:
            # Prepare JSON data with masked sensitive values
            json_data = {}
            for key, value in sorted(filtered.items()):
                if value is None:
                    continue
                value_str = str(value)
                # Mask sensitive values
                if any(
                    sensitive in key.upper()
                    for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY", "PAT"]
                ):
                    json_data[key] = (
                        "***" + value_str[-4:] if len(value_str) > 4 else "***"
                    )
                else:
                    json_data[key] = value_str

            self.output_json(
                {
                    "scope": scope,
                    "filter": self.filter_prefix if self.filter_prefix else None,
                    "variables": json_data,
                    "total": len(filtered),
                }
            )
            return

        self.show_header(
            title="Configuration List",
            project=self.project_name,
            details={
                "Filter": self.filter_prefix if self.filter_prefix else "All",
                "Scope": f"App: {self.app} (merged)" if self.app else "Shared only",
            },
        )

        # Create table
        table = Table(title=f"Configuration Variables - {scope}", padding=(0, 1))
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        # Add rows
        for key, value in sorted(filtered.items()):
            # Skip None values
            if value is None:
                continue

            value_str = str(value)

            # Mask sensitive values
            if any(
                sensitive in key.upper()
                for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY", "PAT"]
            ):
                masked_value = "***" + value_str[-4:] if len(value_str) > 4 else "***"
                table.add_row(key, masked_value)
            else:
                display_value = (
                    value_str[:50] + "..." if len(value_str) > 50 else value_str
                )
                table.add_row(key, display_value)

        self.console.print(table)
        self.console.print()
        self.console.print(f"[dim]Total: {len(filtered)} variables[/dim]")


class ConfigUnsetCommand(ProjectCommand):
    """Unset (delete) configuration variable (Heroku-like!)."""

    def __init__(
        self,
        project_name: str,
        key: str,
        app: str = None,
        environment: str = "production",
        deploy: bool = False,
        no_sync: bool = False,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.key = key
        self.app = app
        self.environment = environment
        self.deploy = deploy
        self.no_sync = no_sync

    def execute(self) -> None:
        """Execute config:unset command - Database-backed."""
        from cli.logger import DeployLogger
        from cli.secret_manager import SecretManager

        self.show_header(
            title="Unset Configuration",
            project=self.project_name,
            details={"Key": self.key},
        )

        logger = DeployLogger(self.project_name, "config-unset", verbose=False)

        # Step 1: Remove from database
        if logger:
            logger.step("[1/3] Removing from Database")

        secret_mgr = SecretManager(
            self.project_root, self.project_name, self.environment
        )

        try:
            # Delete secret from database
            deleted = secret_mgr.delete_secret(self.app, self.key)

            if not deleted:
                self.exit_with_error(f"Secret '{self.key}' not found")

            location = f"app:{self.app}" if self.app else "shared"
            if logger:
                logger.log(f"✓ Removed {self.key} from {location}")

        except Exception as e:
            if logger:
                logger.log_error(f"Failed to delete secret: {e}")
            self.exit_with_error(str(e))

        # Determine where to remove from
        if self.app:
            # Remove from app-specific
            if self.app not in secrets_data["secrets"]:
                self.exit_with_error(
                    f"App '{self.app}' not found in secrets configuration"
                )

            target_dict = secrets_data["secrets"][self.app]
            location = f"secrets.{self.app}"
        else:
            # Remove from shared
            if "shared" not in secrets_data["secrets"]:
                self.exit_with_error("No shared secrets found")

            target_dict = secrets_data["secrets"]["shared"]
            location = "secrets.shared"

        # Check if key exists
        if target_dict is None or self.key not in target_dict:
            self.exit_with_error(f"{self.key} not found in {location}")

        # Remove key
        target_dict.pop(self.key)

        # Write back
        with open(secrets_file, "w") as f:
            yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

        if logger:
            logger.log(f"✓ Removed {self.key} from {location}")

        # Step 2: Sync to GitHub (removes from there too)
        if not self.no_sync:
            if logger:
                logger.step("[2/3] Syncing to GitHub")
            if logger:
                logger.log(
                    f"Clearing and re-syncing to remove deleted secret ({self.environment})..."
                )

            try:
                import sys

                sync_cmd = [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"{self.project_name}:sync",
                    "-e",
                    self.environment,
                    "--clear",  # Clear all secrets then re-sync
                ]

                result = subprocess.run(
                    sync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0:
                    if logger:
                        logger.log(
                            f"✓ Remote secrets updated ({self.environment} - secret removed)"
                        )
                else:
                    if logger:
                        logger.warning("⚠ Sync had issues")
                    if result.stderr:
                        for line in result.stderr.split("\n")[:3]:
                            if line.strip():
                                if logger:
                                    logger.warning(f"  {line}")
            except subprocess.TimeoutExpired:
                if logger:
                    logger.warning("⚠ Sync timed out")
            except Exception as e:
                if logger:
                    logger.log_error(f"Sync failed: {e}")
        else:
            if logger:
                logger.step("[2/3] Skipping Sync")
            if logger:
                logger.log("--no-sync flag provided")

        # Step 3: Trigger Deployment
        if self.deploy:
            if logger:
                logger.step("[3/3] Triggering Deployment")
            if logger:
                logger.log("Redeploying to apply changes...")

            # Load project config
            project_config_file = (
                self.project_root / "projects" / self.project_name / "config.yml"
            )
            with open(project_config_file) as f:
                config = yaml.safe_load(f)

            apps = config.get("apps", {})

            for app_name, app_config in apps.items():
                app_path = Path(app_config.get("path", ""))

                if not app_path.exists():
                    continue

                try:
                    subprocess.run(
                        [
                            "git",
                            "commit",
                            "--allow-empty",
                            "-m",
                            f"config: unset {self.key}",
                        ],
                        cwd=app_path,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "push", "origin", "production"],
                        cwd=app_path,
                        capture_output=True,
                        check=True,
                    )
                    if logger:
                        logger.log(f"  ✓ {app_name} redeployed")
                except Exception:
                    # Silently ignore deployment errors for individual apps
                    pass
        else:
            if logger:
                logger.step("[3/3] Skipping Deployment")
            if logger:
                logger.log("Run with --deploy to redeploy")

        self.console.print()
        self.console.print(f"[bold green]✅ {self.key} removed![/bold green]")
        self.console.print()

        if self.deploy:
            self.console.print(
                f"[dim]💡 Tip: Check status with 'superdeploy {self.project_name}:status'[/dim]"
            )
        else:
            self.console.print(
                "[dim]💡 Tip: Run with --deploy to trigger deployment[/dim]"
            )


class ConfigShowCommand(ProjectCommand):
    """Show all project and orchestrator configuration."""

    def __init__(
        self,
        project_name: str,
        mask: bool = False,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.mask = mask

    def execute(self) -> None:
        """Execute config:show command."""
        from rich.box import ROUNDED
        from cli.secret_manager import SecretManager

        self.show_header(
            title="Show Configuration",
            project=self.project_name,
            details={"Masked": "Yes" if self.mask else "No"},
        )

        # Load project secrets from database
        try:
            secret_mgr = SecretManager(self.project_root, self.project_name)
            secrets_data = secret_mgr.load_secrets()
            env_vars = secrets_data.get("secrets", {}).get("shared", {})
        except Exception:
            self.exit_with_error(f"Project '{self.project_name}' not found")

        # Load orchestrator config
        orchestrator_config_path = (
            self.project_root / "shared" / "orchestrator" / "config.yml"
        )
        orchestrator_config = {}
        if orchestrator_config_path.exists():
            with open(orchestrator_config_path) as f:
                orchestrator_config = yaml.safe_load(f) or {}

        # Load project config
        project_config_path = (
            self.project_root / "projects" / self.project_name / "config.yml"
        )
        project_config = {}
        if project_config_path.exists():
            with open(project_config_path) as f:
                project_config = yaml.safe_load(f) or {}

        # Try to get Terraform outputs for IPs
        try:
            tf_outputs = get_terraform_outputs(self.project_name)
        except Exception:
            tf_outputs = {}

        def mask_value(key, value):
            """Mask sensitive values if --mask flag is set"""
            if not self.mask:
                return value

            sensitive_keywords = ["PASSWORD", "TOKEN", "SECRET", "KEY", "PASS"]
            if any(kw in key.upper() for kw in sensitive_keywords):
                return "***" + value[-4:] if len(value) > 4 else "***"
            return value

        # Group configurations by type
        config_groups = {
            "Caddy": [],
            "GitHub": [],
            "MongoDB": [],
            "Postgres": [],
            "RabbitMQ": [],
            "Redis": [],
            "Elasticsearch": [],
            "Monitoring": [],
            "VMs & Network": [],
            "SSH & Cloud": [],
            "Other": [],
        }

        # Categorize environment variables
        for key in sorted(env_vars.keys()):
            value = env_vars[key]
            # Skip None values
            if value is None:
                continue
            # Convert to string
            value = str(value)
            # Skip empty strings
            if not value.strip():
                continue

            display_value = mask_value(key, value)

            if key.startswith("CADDY_"):
                config_groups["Caddy"].append((key, display_value))
            elif key.startswith("GITHUB_"):
                config_groups["GitHub"].append((key, display_value))
            elif key.startswith("MONGODB_"):
                config_groups["MongoDB"].append((key, display_value))
            elif key.startswith("POSTGRES_"):
                config_groups["Postgres"].append((key, display_value))
            elif key.startswith("RABBITMQ_"):
                config_groups["RabbitMQ"].append((key, display_value))
            elif key.startswith("REDIS_"):
                config_groups["Redis"].append((key, display_value))
            elif key.startswith("ELASTICSEARCH_"):
                config_groups["Elasticsearch"].append((key, display_value))
            elif key.startswith(("PROMETHEUS_", "GRAFANA_")):
                config_groups["Monitoring"].append((key, display_value))
            elif "_IP" in key or key.startswith("GCP_") or "SUBNET" in key:
                config_groups["VMs & Network"].append((key, display_value))
            elif key.startswith("SSH_"):
                config_groups["SSH & Cloud"].append((key, display_value))
            else:
                config_groups["Other"].append((key, display_value))

        # Add VM IPs from Terraform
        if tf_outputs and "vm_external_ips" in tf_outputs:
            external_ips = tf_outputs["vm_external_ips"].get("value", {})
            for vm_name, ip in sorted(external_ips.items()):
                config_groups["VMs & Network"].append(
                    (f"{vm_name.upper()}_EXTERNAL_IP", ip)
                )

        if tf_outputs and "vm_internal_ips" in tf_outputs:
            internal_ips = tf_outputs["vm_internal_ips"].get("value", {})
            for vm_name, ip in sorted(internal_ips.items()):
                config_groups["VMs & Network"].append(
                    (f"{vm_name.upper()}_INTERNAL_IP", ip)
                )

        # Display all configs in one table with section headers
        main_table = Table(
            title=f"[bold white]All Configuration - {self.project_name}[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="cyan",
            padding=(0, 1),
        )
        main_table.add_column("Key", style="cyan", no_wrap=True, width=40)
        main_table.add_column("Value", style="green")

        for group_name, items in config_groups.items():
            if not items:
                continue

            # Add section header
            main_table.add_row(f"[bold yellow]{group_name.title()}[/bold yellow]", "")

            # Add items in this group
            for key, value in items:
                main_table.add_row(f"  {key}", value)

        # Add Orchestrator Information to main table
        if orchestrator_config:
            main_table.add_row("[bold yellow]Orchestrator[/bold yellow]", "")

            # VM info
            if "vm" in orchestrator_config:
                vm = orchestrator_config["vm"]
                if "external_ip" in vm:
                    main_table.add_row("  ORCHESTRATOR_EXTERNAL_IP", vm["external_ip"])
                if "internal_ip" in vm:
                    main_table.add_row("  ORCHESTRATOR_INTERNAL_IP", vm["internal_ip"])

        # Add Connection URLs section
        main_table.add_row("[bold yellow]Connection URLs[/bold yellow]", "")

        # Get external IP for connections
        external_ip = None
        if tf_outputs and "vm_external_ips" in tf_outputs:
            external_ips = tf_outputs["vm_external_ips"].get("value", {})
            # Get first available IP (usually core-0)
            for vm_name, ip in external_ips.items():
                if "core" in vm_name:
                    external_ip = ip
                    break

        # Fallback: try from env_vars
        if not external_ip:
            external_ip = env_vars.get("CORE_0_EXTERNAL_IP") or env_vars.get(
                "CORE-0_EXTERNAL_IP"
            )

        if external_ip:
            # RabbitMQ tunnel info
            rabbitmq_user = env_vars.get("RABBITMQ_USER") or f"{self.project_name}_user"
            if not self.mask and rabbitmq_user:
                main_table.add_row(
                    "  RabbitMQ Management (tunnel)",
                    f"http://localhost:25672/ (user: {rabbitmq_user})",
                )
            else:
                main_table.add_row(
                    "  RabbitMQ Management (tunnel)", "http://localhost:25672/"
                )

            # Postgres tunnel info
            postgres_user = env_vars.get("POSTGRES_USER") or f"{self.project_name}_user"
            postgres_db = env_vars.get("POSTGRES_DB") or f"{self.project_name}_db"
            if not self.mask and postgres_user:
                main_table.add_row(
                    "  Postgres (tunnel)",
                    f"postgresql://{postgres_user}@localhost:5433/{postgres_db}",
                )
            else:
                main_table.add_row(
                    "  Postgres (tunnel)", "postgresql://localhost:5433/"
                )

        # Project domains
        if project_config and "apps" in project_config:
            for app_name, app_config in project_config["apps"].items():
                if "domain" in app_config:
                    main_table.add_row(
                        f"  {app_name.title()} App", f"https://{app_config['domain']}"
                    )

        # Add SSH and Tunnel commands section
        if external_ip and project_config:
            ssh_key = (
                project_config.get("cloud", {})
                .get("ssh", {})
                .get("key_path", "~/.ssh/superdeploy_deploy")
            )
            ssh_user = (
                project_config.get("cloud", {})
                .get("ssh", {})
                .get("user", "superdeploy")
            )

            main_table.add_row("[bold yellow]SSH & Tunnel Access[/bold yellow]", "")

            # SSH command
            main_table.add_row(
                "  SSH to Core VM", f"ssh -i {ssh_key} {ssh_user}@{external_ip}"
            )

            # Tunnel commands
            main_table.add_row(
                "  RabbitMQ Tunnel", f"superdeploy {self.project_name}:tunnel rabbitmq"
            )
            main_table.add_row(
                "  Postgres Tunnel", f"superdeploy {self.project_name}:tunnel postgres"
            )

        # Print the complete table
        self.console.print(main_table)
        self.console.print()


# ============================================================================
# Click Command Wrappers
# ============================================================================


@click.command(name="config:set")
@click.argument("key_value")
@click.option(
    "-a",
    "--app",
    help="App name (api, dashboard, services). If not specified, applies to all apps",
)
@click.option(
    "-e",
    "--env",
    "environment",
    default="production",
    help="Environment (production/staging)",
)
@click.option(
    "--deploy", is_flag=True, help="Auto-deploy after setting config (Heroku-like!)"
)
@click.option("--no-sync", is_flag=True, help="Skip GitHub sync")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def config_set(
    project, key_value, app, environment, deploy, no_sync, verbose, json_output
):
    """
    Set configuration variable (Heroku-like!)

    Updates database secrets, syncs to GitHub, and optionally triggers deployment.

    \b
    Examples:
      # Update env variable
      superdeploy cheapa:config:set DB_HOST=10.0.0.5

      # Update + auto-deploy (Heroku-like!)
      superdeploy cheapa:config:set API_KEY=xyz --deploy

      # Update for specific app only
      superdeploy cheapa:config:set STRIPE_API_KEY=sk_live_xyz -a api --deploy
    """
    cmd = ConfigSetCommand(
        project,
        key_value,
        app=app,
        environment=environment,
        deploy=deploy,
        no_sync=no_sync,
        verbose=verbose,
    )
    cmd.run()


@click.command(name="config:get")
@click.argument("key")
@click.option(
    "-a",
    "--app",
    help="App name (api, storefront, services). If not specified, searches in shared",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def config_get(project, key, app, verbose, json_output):
    """
    Get configuration variable (Heroku-like!)

    \b
    Examples:
      superdeploy cheapa:config:get POSTGRES_PASSWORD
      superdeploy cheapa:config:get AUTH_SECRET -a storefront
    """
    cmd = ConfigGetCommand(
        project, key, app=app, verbose=verbose, json_output=json_output
    )
    cmd.run()


@click.command(name="config:list")
@click.option("--filter", help="Filter by prefix (e.g., POSTGRES, REDIS)")
@click.option(
    "-a",
    "--app",
    help="App name. If specified, shows merged secrets (shared + app-specific)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def config_list(project, filter, app, verbose, json_output):
    """
    List all configuration variables (Heroku-like!)

    \b
    Examples:
      superdeploy cheapa:config:list                       # Shared secrets
      superdeploy cheapa:config:list -a storefront         # Merged secrets for storefront
      superdeploy cheapa:config:list --filter POSTGRES     # Only POSTGRES_* vars
    """
    cmd = ConfigListCommand(
        project, filter_prefix=filter, app=app, verbose=verbose, json_output=json_output
    )
    cmd.run()


@click.command(name="config:unset")
@click.argument("key")
@click.option(
    "-a",
    "--app",
    help="App name (api, storefront, services). If not specified, removes from shared",
)
@click.option(
    "-e",
    "--env",
    "environment",
    default="production",
    help="Environment (production/staging)",
)
@click.option("--deploy", is_flag=True, help="Auto-deploy after unsetting config")
@click.option("--no-sync", is_flag=True, help="Skip GitHub sync")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def config_unset(project, key, app, environment, deploy, no_sync, verbose, json_output):
    """
    Unset (delete) configuration variable (Heroku-like!)

    \b
    Examples:
      superdeploy cheapa:config:unset OLD_API_KEY
      superdeploy cheapa:config:unset LEGACY_TOKEN --deploy
    """
    cmd = ConfigUnsetCommand(
        project,
        key,
        app=app,
        environment=environment,
        deploy=deploy,
        no_sync=no_sync,
        verbose=verbose,
    )
    cmd.run()


@click.command(name="config:show")
@click.option("--mask", is_flag=True, help="Mask sensitive values")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def config_show(project, mask, verbose, json_output):
    """
    Show all project and orchestrator configuration

    \b
    Examples:
      superdeploy cheapa:config:show           # Show all configs
      superdeploy cheapa:config:show --mask    # Mask passwords
    """
    cmd = ConfigShowCommand(
        project, mask=mask, verbose=verbose, json_output=json_output
    )
    cmd.run()
