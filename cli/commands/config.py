"""SuperDeploy CLI - Config command"""

import click
import subprocess
import yaml
from rich.console import Console
from rich.table import Table
from cli.utils import load_env, get_project_root
from cli.terraform_utils import get_terraform_outputs

console = Console()


@click.command(name="config:set")
@click.argument("key_value")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def config_set(key_value, app, environment):
    """
    Set configuration variable in GitHub Environment

    \b
    Examples:
      superdeploy config:set API_DEBUG=false -a api
      superdeploy config:set SENTRY_DSN=https://... -a api
    """
    env_vars = load_env()

    # Parse key=value
    try:
        key, value = key_value.split("=", 1)
    except ValueError:
        console.print("[red]❌ Invalid format! Use: KEY=VALUE[/red]")
        raise SystemExit(1)

    # Get GitHub org from environment or project config
    github_org = env_vars.get("GITHUB_ORG", f"{project}io")

    # Map app to GitHub repo (project-aware)
    repos = {
        "api": env_vars.get("GITHUB_REPO_API", f"{github_org}/api"),
        "dashboard": env_vars.get("GITHUB_REPO_DASHBOARD", f"{github_org}/dashboard"),
        "services": env_vars.get("GITHUB_REPO_SERVICES", f"{github_org}/services"),
    }

    repo = repos.get(app)
    if not repo:
        console.print(f"[red]❌ Unknown app: {app}[/red]")
        raise SystemExit(1)

    console.print(
        f"[cyan]Setting [bold]{key}[/bold] for [bold]{app}[/bold] ({environment})...[/cyan]"
    )

    try:
        # Use gh CLI to set secret
        subprocess.run(
            ["gh", "secret", "set", key, "-b", value, "-e", environment, "-R", repo],
            check=True,
            capture_output=True,
        )

        console.print(f"[green]✅ {key} set successfully![/green]")
        console.print("[dim]Note: Redeploy for changes to take effect[/dim]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to set secret: {e.stderr.decode()}[/red]")
        raise SystemExit(1)


@click.command(name="config:get")
@click.argument("key")
@click.option("-a", "--app", required=True, help="App name")
def config_get(key, app):
    """
    Get configuration variable (from local .env)

    \b
    Examples:
      superdeploy config:get POSTGRES_PASSWORD -a api
    """
    env_vars = load_env()

    value = env_vars.get(key)

    if value:
        console.print(f"[cyan]{key}[/cyan]=[green]{value}[/green]")
    else:
        console.print(f"[yellow]⚠️  {key} not found in .env[/yellow]")
        raise SystemExit(1)


@click.command(name="config:list")
@click.option("-a", "--app", help="Filter by app")
def config_list(app):
    """
    List all configuration variables

    \b
    Examples:
      superdeploy config:list           # All vars
      superdeploy config:list -a api    # App-specific
    """
    env_vars = load_env()

    # Create table
    table = Table(title="Configuration Variables")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    # App-specific filtering
    if app:
        # Show only app-related vars - get prefixes dynamically
        from cli.commands.env import get_addon_prefixes

        prefixes = [f"{p}_" for p in get_addon_prefixes(None)]  # None = use fallback
        filtered = {
            k: v for k, v in env_vars.items() if any(k.startswith(p) for p in prefixes)
        }
    else:
        filtered = env_vars

    # Add rows
    for key, value in sorted(filtered.items()):
        # Mask sensitive values
        if any(
            sensitive in key.upper()
            for sensitive in ["PASSWORD", "TOKEN", "SECRET", "KEY"]
        ):
            masked_value = "***" + value[-4:] if len(value) > 4 else "***"
            table.add_row(key, masked_value)
        else:
            table.add_row(key, value[:50] + "..." if len(value) > 50 else value)

    console.print(table)


@click.command(name="config:unset")
@click.argument("key")
@click.option("-a", "--app", required=True, help="App name")
@click.option("-e", "--env", "environment", default="production", help="Environment")
def config_unset(key, app, environment):
    """
    Unset (delete) configuration variable

    \b
    Examples:
      superdeploy config:unset SENTRY_DSN -a api
    """
    # Map app to GitHub repo
    env_vars = load_env()

    # Get GitHub org from environment or project config
    github_org = env_vars.get("GITHUB_ORG", f"{project}io")

    repos = {
        "api": env_vars.get("GITHUB_REPO_API", f"{github_org}/api"),
        "dashboard": env_vars.get("GITHUB_REPO_DASHBOARD", f"{github_org}/dashboard"),
        "services": env_vars.get("GITHUB_REPO_SERVICES", f"{github_org}/services"),
    }

    repo = repos.get(app)
    if not repo:
        console.print(f"[red]❌ Unknown app: {app}[/red]")
        raise SystemExit(1)

    console.print(
        f"[yellow]Removing [bold]{key}[/bold] from [bold]{app}[/bold] ({environment})...[/yellow]"
    )

    try:
        # Use gh CLI to delete secret
        subprocess.run(
            ["gh", "secret", "delete", key, "-e", environment, "-R", repo],
            check=True,
            capture_output=True,
        )

        console.print(f"[green]✅ {key} removed successfully![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to delete secret: {e.stderr.decode()}[/red]")
        raise SystemExit(1)


@click.command(name="config:show")
@click.option("-p", "--project", required=True, help="Project name")
@click.option("--mask", is_flag=True, help="Mask sensitive values")
def config_show(project, mask):
    """
    Show all project and orchestrator configuration

    \b
    Examples:
      superdeploy config:show -p cheapa           # Show all configs
      superdeploy config:show -p cheapa --mask    # Mask passwords
    """
    project_root = get_project_root()

    console.print(f"\n[bold cyan]🔧 Configuration for: {project}[/bold cyan]\n")

    # Load project .env
    try:
        env_vars = load_env(project)
    except:
        console.print(f"[red]❌ Project '{project}' not found[/red]")
        raise SystemExit(1)

    # Load orchestrator config
    orchestrator_config_path = project_root / "shared" / "orchestrator" / "config.yml"
    orchestrator_config = {}
    if orchestrator_config_path.exists():
        with open(orchestrator_config_path) as f:
            orchestrator_config = yaml.safe_load(f) or {}

    # Load project config
    project_config_path = project_root / "projects" / project / "project.yml"
    project_config = {}
    if project_config_path.exists():
        with open(project_config_path) as f:
            project_config = yaml.safe_load(f) or {}

    # Try to get Terraform outputs for IPs
    try:
        tf_outputs = get_terraform_outputs(project)
    except:
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
        "Forgejo": [],
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
        elif key.startswith("FORGEJO_"):
            config_groups["Forgejo"].append((key, display_value))
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

    # Display each group
    from rich.box import ROUNDED

    for group_name, items in config_groups.items():
        if not items:
            continue

        table = Table(
            title=f"[bold white]{group_name}[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="cyan",
        )
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        for key, value in items:
            table.add_row(key, value)

        console.print(table)
        console.print()

    # Show Orchestrator Information
    if orchestrator_config:
        orch_table = Table(
            title="[bold white]📦 Orchestrator Configuration[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="magenta",
        )
        orch_table.add_column("Key", style="cyan", no_wrap=True)
        orch_table.add_column("Value", style="green")

        # Forgejo info
        if "forgejo" in orchestrator_config:
            forgejo = orchestrator_config["forgejo"]
            orch_table.add_row("FORGEJO_DOMAIN", forgejo.get("domain", "N/A"))
            orch_table.add_row("FORGEJO_ADMIN_USER", forgejo.get("admin_user", "N/A"))
            if "admin_password" in forgejo:
                pwd = forgejo["admin_password"]
                orch_table.add_row(
                    "FORGEJO_ADMIN_PASSWORD", mask_value("PASSWORD", pwd)
                )

        # VM info
        if "vm" in orchestrator_config:
            vm = orchestrator_config["vm"]
            if "external_ip" in vm:
                orch_table.add_row("ORCHESTRATOR_EXTERNAL_IP", vm["external_ip"])
            if "internal_ip" in vm:
                orch_table.add_row("ORCHESTRATOR_INTERNAL_IP", vm["internal_ip"])

        console.print(orch_table)
        console.print()

    # Show connection URLs
    urls_table = Table(
        title="[bold white]🔗 Connection URLs[/bold white]",
        show_header=True,
        header_style="bold magenta",
        box=ROUNDED,
        title_style="bold cyan",
        title_justify="left",
        border_style="yellow",
    )
    urls_table.add_column("Service", style="cyan", no_wrap=True)
    urls_table.add_column("URL", style="blue underline")

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
        rabbitmq_pass = env_vars.get("RABBITMQ_PASSWORD", "")
        if not mask and rabbitmq_user:
            urls_table.add_row(
                "RabbitMQ Management (tunnel)",
                f"http://localhost:25672/ (user: {rabbitmq_user})",
            )
        else:
            urls_table.add_row(
                "RabbitMQ Management (tunnel)", "http://localhost:25672/"
            )

        # Postgres tunnel info - use defaults if not set
        postgres_user = env_vars.get("POSTGRES_USER") or f"{project}_user"
        postgres_db = env_vars.get("POSTGRES_DB") or f"{project}_db"
        if not mask and postgres_user:
            urls_table.add_row(
                "Postgres (tunnel)",
                f"postgresql://{postgres_user}@localhost:5433/{postgres_db}",
            )
        else:
            urls_table.add_row("Postgres (tunnel)", "postgresql://localhost:5433/")

    # Orchestrator URLs
    if orchestrator_config and "forgejo" in orchestrator_config:
        domain = orchestrator_config["forgejo"].get("domain")
        if domain:
            urls_table.add_row("Forgejo", f"https://{domain}")

    # Project domains
    if project_config and "apps" in project_config:
        for app_name, app_config in project_config["apps"].items():
            if "domain" in app_config:
                urls_table.add_row(
                    f"{app_name.title()} App", f"https://{app_config['domain']}"
                )

    console.print(urls_table)
    console.print()

    # Show SSH and Tunnel commands
    if external_ip and project_config:
        ssh_key = (
            project_config.get("cloud", {})
            .get("ssh", {})
            .get("key_path", "~/.ssh/superdeploy_deploy")
        )
        ssh_user = (
            project_config.get("cloud", {}).get("ssh", {}).get("user", "superdeploy")
        )

        access_table = Table(
            title="[bold white]🔐 SSH & Tunnel Access[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="green",
        )
        access_table.add_column("Type", style="cyan", no_wrap=True)
        access_table.add_column("Command", style="green")

        # SSH command
        access_table.add_row(
            "SSH to Core VM", f"ssh -i {ssh_key} {ssh_user}@{external_ip}"
        )

        # Tunnel commands
        access_table.add_row(
            "RabbitMQ Tunnel", f"superdeploy tunnel -p {project} rabbitmq"
        )
        access_table.add_row(
            "Postgres Tunnel", f"superdeploy tunnel -p {project} postgres"
        )

        console.print(access_table)
        console.print()
