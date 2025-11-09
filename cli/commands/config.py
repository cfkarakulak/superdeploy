"""SuperDeploy CLI - Config command"""

import click
import subprocess
import yaml
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header
from cli.utils import get_project_root
from cli.terraform_utils import get_terraform_outputs

console = Console()


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
def config_set(key_value, project, app, environment, deploy, no_sync):
    """
    Set configuration variable (Heroku-like!)

    Updates secrets.yml, syncs to GitHub, and optionally triggers deployment.

    \b
    Examples:
      # Update env variable
      superdeploy config:set DB_HOST=10.0.0.5 -p myproject

      # Update + auto-deploy (Heroku-like!)
      superdeploy config:set API_KEY=xyz -p myproject --deploy

      # Update for specific app only
      superdeploy config:set STRIPE_API_KEY=sk_live_xyz myproject: -a api --deploy
    """
    from pathlib import Path
    from cli.utils import get_project_root, validate_project
    from cli.logger import DeployLogger

    # Validate project first
    validate_project(project)

    # Parse key=value
    try:
        key, value = key_value.split("=", 1)
    except ValueError:
        console.print("[red]❌ Invalid format! Use: KEY=VALUE[/red]")
        raise SystemExit(1)

    show_header(
        title="Set Configuration",
        subtitle="Heroku-like config management",
        project=project,
        console=console,
    )

    logger = DeployLogger(project, "config-set", verbose=False)

    project_root = get_project_root()
    secrets_file = project_root / "projects" / project / "secrets.yml"

    # Step 1: Update secrets.yml
    logger.step("[1/4] Updating Local Config")
    logger.log(f"File: {secrets_file}")

    # Load existing secrets with proper structure
    if secrets_file.exists():
        with open(secrets_file) as f:
            secrets_data = yaml.safe_load(f) or {}
    else:
        secrets_data = {}

    # Ensure proper structure
    if "secrets" not in secrets_data:
        secrets_data["secrets"] = {}
    if "shared" not in secrets_data["secrets"]:
        secrets_data["secrets"]["shared"] = {}

    # Determine target location: app-specific or shared
    if app:
        # App-specific secret
        if app not in secrets_data["secrets"]:
            secrets_data["secrets"][app] = {}
        target_dict = secrets_data["secrets"][app]
        location = f"secrets.{app}"
    else:
        # Shared secret (all apps)
        target_dict = secrets_data["secrets"]["shared"]
        location = "secrets.shared"

    # Store old value for logging
    old_value = target_dict.get(key)

    # Update value
    target_dict[key] = value

    # Write back with proper formatting
    with open(secrets_file, "w") as f:
        yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

    if old_value:
        logger.log(f"✓ Updated {key} in {location} (previous value overwritten)")
    else:
        logger.log(f"✓ Added {key} to {location}")

    # Step 2: Sync to GitHub
    if not no_sync:
        logger.step("[2/4] Syncing to GitHub")
        logger.log(f"Running sync command for {environment} environment...")

        try:
            # Use subprocess to call sync command
            # This is more reliable than CliRunner for namespace commands
            import sys

            sync_cmd = [
                sys.executable,
                "-m",
                "cli.main",
                f"{project}:sync",
                "-e",
                environment,
            ]

            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.log(f"✓ Synced to GitHub ({environment})")
            else:
                logger.warning("⚠ Sync had issues")
                if result.stderr:
                    for line in result.stderr.split("\n")[:3]:
                        if line.strip():
                            logger.warning(f"  {line}")
        except subprocess.TimeoutExpired:
            logger.warning("⚠ Sync timed out")
        except Exception as e:
            logger.log_error(f"Sync failed: {e}")
            logger.warning("Continuing without sync...")
    else:
        logger.step("[2/4] Skipping Sync")
        logger.log("--no-sync flag provided")

    # Step 3: Trigger Deployment
    if deploy:
        logger.step("[3/4] Triggering Deployment")

        # Load project config
        project_config_file = project_root / "projects" / project / "config.yml"
        with open(project_config_file) as f:
            config = yaml.safe_load(f)

        apps = config.get("apps", {})

        # Filter apps if -a specified
        if app:
            if app not in apps:
                logger.log_error(f"App '{app}' not found in project config")
                raise SystemExit(1)
            apps = {app: apps[app]}

        # Deploy each app
        deployed_count = 0
        failed_count = 0

        for app_name, app_config in apps.items():
            app_path = Path(app_config.get("path", ""))

            if not app_path.exists():
                logger.warning(f"⚠ {app_name}: path not found ({app_path})")
                failed_count += 1
                continue

            logger.log(f"Deploying {app_name}...")

            try:
                # Empty commit to trigger deployment
                result = subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", f"config: update {key}"],
                    cwd=app_path,
                    capture_output=True,
                    text=True,
                )

                # Push to production
                result = subprocess.run(
                    ["git", "push", "origin", environment],
                    cwd=app_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                logger.log(f"  ✓ {app_name} deployment triggered")
                deployed_count += 1

            except subprocess.CalledProcessError as e:
                logger.log_error(f"  ✗ {app_name} deployment failed: {e.stderr}")
                failed_count += 1

        logger.log("")
        logger.log(
            f"Deployment summary: {deployed_count} succeeded, {failed_count} failed"
        )

        if deployed_count > 0:
            logger.step("[4/4] Deployment In Progress")
            logger.log("✓ Deployment triggered via git push")
            logger.log(f"Watch logs: superdeploy :logs{project} --follow")

    else:
        logger.step("[3/4] Skipping Deployment")
        logger.log("Run with --deploy to auto-deploy")
        logger.log(f"Or manually: cd <app-path> && git push origin {environment}")

    # Summary
    console.print()
    console.print("[bold green]✅ Configuration Updated![/bold green]")
    console.print()
    console.print(f"  [cyan]{key}[/cyan] = [green]{value}[/green]")
    console.print()

    if deploy:
        console.print(
            f"[dim]💡 Tip: Check deployment status with 'superdeploy :status{project}'[/dim]"
        )
    else:
        console.print(
            "[dim]💡 Tip: Run with --deploy to trigger deployment automatically[/dim]"
        )


@click.command(name="config:get")
@click.argument("key")
@click.option(
    "-a",
    "--app",
    help="App name (api, storefront, services). If not specified, searches in shared",
)
def config_get(key, project, app):
    """
    Get configuration variable (Heroku-like!)

    \b
    Examples:
      superdeploy config:get POSTGRES_PASSWORD -p myproject
      superdeploy config:get AUTH_SECRET -p myproject -a storefront
    """
    from cli.utils import validate_project

    validate_project(project)

    show_header(
        title="Get Configuration",
        project=project,
        details={"Key": key, "App": app if app else "shared"},
        console=console,
    )

    # Load from secrets.yml
    from cli.secret_manager import SecretManager

    secret_mgr = SecretManager(get_project_root(), project)
    secrets_data = secret_mgr.load_secrets()

    # Get value from appropriate location
    if app:
        # Get from app-specific secrets
        app_secrets = secret_mgr.get_app_secrets(app)
        value = app_secrets.get(key)
        location = f"secrets.{app} (merged with shared)"
    else:
        # Get from shared secrets only
        shared_secrets = secrets_data.get("secrets", {}).get("shared", {})
        value = shared_secrets.get(key)
        location = "secrets.shared"

    if value:
        # Mask sensitive values
        if any(
            sensitive in key.upper()
            for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY"]
        ):
            masked = "***" + str(value)[-4:] if len(str(value)) > 4 else "***"
            console.print(
                f"[cyan]{key}[/cyan]=[yellow]{masked}[/yellow] [dim](masked, from {location})[/dim]"
            )
        else:
            console.print(
                f"[cyan]{key}[/cyan]=[green]{value}[/green] [dim](from {location})[/dim]"
            )
    else:
        console.print(f"[yellow]⚠️  {key} not found in {location}[/yellow]")
        raise SystemExit(1)


@click.command(name="config:list")
@click.option("--filter", help="Filter by prefix (e.g., POSTGRES, REDIS)")
@click.option(
    "-a",
    "--app",
    help="App name. If specified, shows merged secrets (shared + app-specific)",
)
def config_list(project, filter, app):
    """
    List all configuration variables (Heroku-like!)

    \b
    Examples:
      superdeploy config:list -p myproject                       # Shared secrets
      superdeploy config:list -p myproject -a storefront         # Merged secrets for storefront
      superdeploy config:list -p myproject --filter POSTGRES     # Only POSTGRES_* vars
    """
    from cli.utils import validate_project

    validate_project(project)

    show_header(
        title="Configuration List",
        project=project,
        details={
            "Filter": filter if filter else "All",
            "Scope": f"App: {app} (merged)" if app else "Shared only",
        },
        console=console,
    )

    # Load from secrets.yml
    from cli.secret_manager import SecretManager

    secret_mgr = SecretManager(get_project_root(), project)

    # Get appropriate secrets
    if app:
        # Get merged secrets for app
        env_vars = secret_mgr.get_app_secrets(app)
        scope = f"{app} (shared + app-specific)"
    else:
        # Get only shared secrets
        secrets_data = secret_mgr.load_secrets()
        env_vars = secrets_data.get("secrets", {}).get("shared", {})
        scope = "shared"

    # Create table
    table = Table(title=f"Configuration Variables - {scope}", padding=(0, 1))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Filter if specified
    if filter:
        filtered = {
            k: v for k, v in env_vars.items() if k.upper().startswith(filter.upper())
        }
    else:
        filtered = env_vars

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
            display_value = value_str[:50] + "..." if len(value_str) > 50 else value_str
            table.add_row(key, display_value)

    console.print(table)
    console.print()
    console.print(f"[dim]Total: {len(filtered)} variables[/dim]")


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
def config_unset(key, project, app, environment, deploy, no_sync):
    """
    Unset (delete) configuration variable (Heroku-like!)

    \b
    Examples:
      superdeploy config:unset OLD_API_KEY -p myproject
      superdeploy config:unset LEGACY_TOKEN -p myproject --deploy
    """
    from pathlib import Path
    from cli.utils import get_project_root, validate_project
    from cli.logger import DeployLogger

    validate_project(project)

    show_header(
        title="Unset Configuration",
        project=project,
        details={"Key": key},
        console=console,
    )

    logger = DeployLogger(project, "config-unset", verbose=False)

    project_root = get_project_root()
    secrets_file = project_root / "projects" / project / "secrets.yml"

    # Step 1: Remove from secrets.yml
    logger.step("[1/3] Removing from Local Config")

    if not secrets_file.exists():
        console.print(f"[yellow]⚠️  {secrets_file} not found[/yellow]")
        raise SystemExit(1)

    with open(secrets_file) as f:
        secrets_data = yaml.safe_load(f) or {}

    # Check structure
    if "secrets" not in secrets_data:
        console.print(f"[yellow]⚠️  No secrets found in {secrets_file}[/yellow]")
        raise SystemExit(1)

    # Determine where to remove from
    if app:
        # Remove from app-specific
        if app not in secrets_data["secrets"]:
            console.print(
                f"[yellow]⚠️  App '{app}' not found in secrets configuration[/yellow]"
            )
            raise SystemExit(1)

        target_dict = secrets_data["secrets"][app]
        location = f"secrets.{app}"
    else:
        # Remove from shared
        if "shared" not in secrets_data["secrets"]:
            console.print("[yellow]⚠️  No shared secrets found[/yellow]")
            raise SystemExit(1)

        target_dict = secrets_data["secrets"]["shared"]
        location = "secrets.shared"

    # Check if key exists
    if target_dict is None or key not in target_dict:
        console.print(f"[yellow]⚠️  {key} not found in {location}[/yellow]")
        raise SystemExit(1)

    # Remove key
    target_dict.pop(key)

    # Write back
    with open(secrets_file, "w") as f:
        yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

    logger.log(f"✓ Removed {key} from {location}")

    # Step 2: Sync to GitHub (removes from there too)
    if not no_sync:
        logger.step("[2/3] Syncing to GitHub")
        logger.log(
            f"Clearing and re-syncing to remove deleted secret ({environment})..."
        )

        try:
            # Use subprocess to call sync with --clear flag
            # This ensures the deleted secret is removed from GitHub
            import sys

            sync_cmd = [
                sys.executable,
                "-m",
                "cli.main",
                f"{project}:sync",
                "-e",
                environment,
                "--clear",  # Clear all secrets then re-sync
            ]

            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.log(f"✓ Remote secrets updated ({environment} - secret removed)")
            else:
                logger.warning("⚠ Sync had issues")
                if result.stderr:
                    for line in result.stderr.split("\n")[:3]:
                        if line.strip():
                            logger.warning(f"  {line}")
        except subprocess.TimeoutExpired:
            logger.warning("⚠ Sync timed out")
        except Exception as e:
            logger.log_error(f"Sync failed: {e}")
    else:
        logger.step("[2/3] Skipping Sync")
        logger.log("--no-sync flag provided")

    # Step 3: Trigger Deployment
    if deploy:
        logger.step("[3/3] Triggering Deployment")
        logger.log("Redeploying to apply changes...")

        # Load project config
        project_config_file = project_root / "projects" / project / "config.yml"
        with open(project_config_file) as f:
            config = yaml.safe_load(f)

        apps = config.get("apps", {})

        for app_name, app_config in apps.items():
            app_path = Path(app_config.get("path", ""))

            if not app_path.exists():
                continue

            try:
                subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", f"config: unset {key}"],
                    cwd=app_path,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "push", "origin", "production"],
                    cwd=app_path,
                    capture_output=True,
                    check=True,
                )
                logger.log(f"  ✓ {app_name} redeployed")
            except Exception:
                # Silently ignore deployment errors for individual apps
                pass
    else:
        logger.step("[3/3] Skipping Deployment")
        logger.log("Run with --deploy to redeploy")

    console.print()
    console.print(f"[bold green]✅ {key} removed![/bold green]")
    console.print()

    if deploy:
        console.print(
            f"[dim]💡 Tip: Check status with 'superdeploy :status{project}'[/dim]"
        )
    else:
        console.print("[dim]💡 Tip: Run with --deploy to trigger deployment[/dim]")


@click.command(name="config:show")
@click.option("--mask", is_flag=True, help="Mask sensitive values")
def config_show(project, mask):
    """
    Show all project and orchestrator configuration

    \b
    Examples:
      superdeploy config:show -p cheapa           # Show all configs
      superdeploy config:show -p cheapa --mask    # Mask passwords
    """
    show_header(
        title="Show Configuration",
        project=project,
        details={"Masked": "Yes" if mask else "No"},
        console=console,
    )

    project_root = get_project_root()

    # Load project secrets from secrets.yml
    try:
        from cli.secret_manager import SecretManager

        secret_mgr = SecretManager(project_root, project)
        secrets_data = secret_mgr.load_secrets()
        env_vars = secrets_data.get("secrets", {}).get("shared", {})
    except Exception:
        console.print(f"[red]❌ Project '{project}' not found[/red]")
        raise SystemExit(1)

    # Load orchestrator config
    orchestrator_config_path = project_root / "shared" / "orchestrator" / "config.yml"
    orchestrator_config = {}
    if orchestrator_config_path.exists():
        with open(orchestrator_config_path) as f:
            orchestrator_config = yaml.safe_load(f) or {}

    # Load project config
    project_config_path = project_root / "projects" / project / "config.yml"
    project_config = {}
    if project_config_path.exists():
        with open(project_config_path) as f:
            project_config = yaml.safe_load(f) or {}

    # Try to get Terraform outputs for IPs
    try:
        tf_outputs = get_terraform_outputs(project)
    except Exception:
        tf_outputs = {}

    def mask_value(key, value):
        """Mask sensitive values if --mask flag is set"""
        if not mask:
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
    from rich.box import ROUNDED

    main_table = Table(
        title=f"[bold white]All Configuration - {project}[/bold white]",
        show_header=True,
        header_style="bold magenta",
        box=ROUNDED,
        title_style="bold cyan",
        title_justify="left",
        border_style="cyan",
        padding=(0, 1),  # Reduce vertical padding (top/bottom, left/right)
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
        # RabbitMQ tunnel info - use defaults if not set
        rabbitmq_user = env_vars.get("RABBITMQ_USER") or f"{project}_user"
        if not mask and rabbitmq_user:
            main_table.add_row(
                "  RabbitMQ Management (tunnel)",
                f"http://localhost:25672/ (user: {rabbitmq_user})",
            )
        else:
            main_table.add_row(
                "  RabbitMQ Management (tunnel)", "http://localhost:25672/"
            )

        # Postgres tunnel info - use defaults if not set
        postgres_user = env_vars.get("POSTGRES_USER") or f"{project}_user"
        postgres_db = env_vars.get("POSTGRES_DB") or f"{project}_db"
        if not mask and postgres_user:
            main_table.add_row(
                "  Postgres (tunnel)",
                f"postgresql://{postgres_user}@localhost:5433/{postgres_db}",
            )
        else:
            main_table.add_row("  Postgres (tunnel)", "postgresql://localhost:5433/")

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
            project_config.get("cloud", {}).get("ssh", {}).get("user", "superdeploy")
        )

        main_table.add_row("[bold yellow]SSH & Tunnel Access[/bold yellow]", "")

        # SSH command
        main_table.add_row(
            "  SSH to Core VM", f"ssh -i {ssh_key} {ssh_user}@{external_ip}"
        )

        # Tunnel commands
        main_table.add_row(
            "  RabbitMQ Tunnel", f"superdeploy :tunnel{project} rabbitmq"
        )
        main_table.add_row(
            "  Postgres Tunnel", f"superdeploy :tunnel{project} postgres"
        )

    # Print the complete table
    console.print(main_table)
    console.print()
