"""SuperDeploy CLI - Orchestrator command (with improved logging and UX)"""

import click
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from cli.utils import get_project_root
from cli.logger import DeployLogger, run_with_progress

console = Console()


@click.group()
def orchestrator():
    """Manage global Forgejo orchestrator"""
    pass


@orchestrator.command()
def init():
    """Initialize orchestrator configuration (interactive wizard)"""
    from rich.prompt import Prompt, Confirm
    
    console.print(
        Panel.fit(
            "[bold cyan]🎯 SuperDeploy Orchestrator Setup[/bold cyan]\n\n"
            "[white]Let's configure your global orchestrator (Forgejo + Monitoring)[/white]",
            border_style="cyan",
        )
    )
    
    project_root = get_project_root()
    shared_dir = project_root / "shared"
    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = orchestrator_dir / "config.yml"
    template_path = orchestrator_dir / "config.template.yml"
    
    # Check if config already exists
    if config_path.exists():
        overwrite = Confirm.ask(
            "\n[yellow]⚠️  Orchestrator config already exists. Overwrite?[/yellow]",
            default=False
        )
        if not overwrite:
            console.print("\n[dim]Cancelled. Existing config preserved.[/dim]")
            return
    
    # Check if template exists
    if not template_path.exists():
        console.print(f"\n[red]❌ Template not found: {template_path}[/red]")
        raise SystemExit(1)
    
    console.print("\n[bold cyan]📋 Cloud Configuration[/bold cyan]")
    console.print("[dim]Configure your GCP project and region[/dim]\n")
    
    gcp_project = Prompt.ask(
        "  [cyan]GCP Project ID[/cyan]",
        default=""
    )
    
    region = Prompt.ask(
        "  [cyan]GCP Region[/cyan]",
        default="us-central1"
    )
    
    zone = Prompt.ask(
        "  [cyan]GCP Zone[/cyan]",
        default=f"{region}-a"
    )
    
    console.print("\n[bold cyan]🔐 SSL Configuration[/bold cyan]")
    console.print("[dim]Email for Let's Encrypt SSL certificates[/dim]\n")
    
    ssl_email = Prompt.ask(
        "  [cyan]SSL Email[/cyan]",
        default=""
    )
    
    console.print("\n[bold cyan]🔧 Forgejo Configuration[/bold cyan]")
    console.print("[dim]Git server with CI/CD capabilities[/dim]\n")
    
    admin_user = Prompt.ask(
        "  [cyan]Admin Username[/cyan]",
        default="admin"
    )
    
    admin_email = Prompt.ask(
        "  [cyan]Admin Email[/cyan]",
        default=""
    )
    
    org = Prompt.ask(
        "  [cyan]Organization Name[/cyan]",
        default=""
    )
    
    console.print("\n[bold cyan]📊 Global Monitoring Configuration[/bold cyan]")
    console.print("[dim]Grafana and Prometheus will monitor ALL projects[/dim]")
    console.print("[dim]Optional: Enable HTTPS with custom domains (e.g., grafana.cfk.com)[/dim]\n")
    
    enable_domains = Confirm.ask(
        "  [cyan]Configure custom domains?[/cyan]",
        default=False
    )
    
    grafana_domain = ""
    prometheus_domain = ""
    forgejo_domain = ""
    enable_caddy = False
    
    if enable_domains:
        grafana_domain = Prompt.ask(
            "  [cyan]Grafana Domain[/cyan] (global monitoring for all projects)",
            default=""
        )
        prometheus_domain = Prompt.ask(
            "  [cyan]Prometheus Domain[/cyan] (global metrics for all projects)",
            default=""
        )
        forgejo_domain = Prompt.ask(
            "  [cyan]Forgejo Domain[/cyan] (git server for all projects)",
            default=""
        )
        enable_caddy = True
    
    # Read template
    with open(template_path, 'r') as f:
        config_content = f.read()
    
    # Replace placeholders
    config_content = config_content.replace('YOUR_GCP_PROJECT_ID', gcp_project)
    config_content = config_content.replace('region: "us-central1"', f'region: "{region}"')
    config_content = config_content.replace('zone: "us-central1-a"', f'zone: "{zone}"')
    config_content = config_content.replace('ssl_email: ""', f'ssl_email: "{ssl_email}"')
    config_content = config_content.replace('YOUR_USERNAME', admin_user)
    config_content = config_content.replace('YOUR_EMAIL@example.com', admin_email)
    config_content = config_content.replace('YOUR_ORG', org)
    
    # Update domains if configured
    if enable_domains:
        config_content = config_content.replace('grafana:\n  domain: ""', f'grafana:\n  domain: "{grafana_domain}"')
        config_content = config_content.replace('prometheus:\n  domain: ""', f'prometheus:\n  domain: "{prometheus_domain}"')
        config_content = config_content.replace('forgejo:\n  domain: ""', f'forgejo:\n  domain: "{forgejo_domain}"')
        config_content = config_content.replace('enabled: false  # Set to true', 'enabled: true  # Set to true')
    
    # Update header
    config_content = config_content.replace(
        '# Orchestrator Configuration Template',
        '# Orchestrator Configuration'
    )
    config_content = config_content.replace(
        '# Copy this to config.yml and customize for your setup',
        '# Auto-generated by: superdeploy orchestrator init'
    )
    
    # Write config
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]✅ Orchestrator Configured![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(f"\n[cyan]📄 Config saved to:[/cyan] {config_path}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. [dim]Review config:[/dim] shared/orchestrator/config.yml")
    console.print("  2. [dim]Deploy orchestrator:[/dim] [cyan]superdeploy orchestrator up[/cyan]")
    
    if enable_domains:
        console.print("\n[yellow]⚠️  Don't forget to:[/yellow]")
        console.print("  • Point DNS A records to orchestrator IP")
        console.print("  • Wait for DNS propagation before deployment")
    
    console.print()


@orchestrator.command()
@click.option(
    "--skip-terraform", is_flag=True, help="Skip Terraform (VM already exists)"
)
@click.option(
    "--preserve-ip", is_flag=True, help="Preserve static IP on destroy (for production)"
)
@click.option(
    "--addon",
    help="Deploy only specific addon(s), comma-separated (e.g. --addon monitoring,caddy)",
)
@click.option(
    "--tags", help="Run only specific Ansible tags (e.g. 'addons', 'foundation')"
)
@click.option(
    "--start-at-task",
    help="Resume Ansible from a specific task (e.g. 'Install Docker'). Saves time when rerunning after failures.",
)
@click.option(
    "--verbose", "-v", is_flag=True, help="Show all command output (default: clean UI with logs)"
)
def up(skip_terraform, preserve_ip, addon, tags, start_at_task, verbose):
    """Deploy orchestrator VM with Forgejo (runs Terraform + Ansible by default)"""
    console.print(
        Panel.fit(
            "[bold cyan]🚀 Deploying Global Orchestrator[/bold cyan]\n\n"
            "[white]This will deploy a shared Forgejo instance for all projects[/white]",
            border_style="cyan",
        )
    )

    project_root = get_project_root()
    shared_dir = project_root / "shared"

    # Load orchestrator config
    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    # Generate and save secrets FIRST (before any checks)
    console.print("\n[cyan]🔐 Checking secrets...[/cyan]")
    import secrets as secrets_module

    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    env_file = orchestrator_dir / ".env"

    # Check if secrets already exist
    if env_file.exists():
        console.print("[dim]✓ Using existing orchestrator secrets from .env[/dim]")
        # Load existing secrets
        project_secrets = {}
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    project_secrets[key] = value
    else:
        # Generate new secrets
        console.print("[cyan]Generating new orchestrator secrets...[/cyan]")
        project_secrets = {
            "FORGEJO_ADMIN_PASSWORD": secrets_module.token_urlsafe(32),
            "FORGEJO_DB_PASSWORD": secrets_module.token_urlsafe(32),
            "FORGEJO_SECRET_KEY": secrets_module.token_urlsafe(48),  # 64 chars
            "FORGEJO_INTERNAL_TOKEN": secrets_module.token_urlsafe(79),  # 105 chars
            "GRAFANA_ADMIN_PASSWORD": secrets_module.token_urlsafe(32),
        }

        # Save secrets to .env file
        env_content = """# =============================================================================
# Orchestrator Secrets
# =============================================================================
# Auto-generated by: superdeploy orchestrator up
# DO NOT COMMIT THIS FILE TO GIT!
# =============================================================================

# Forgejo Admin Password
FORGEJO_ADMIN_PASSWORD={FORGEJO_ADMIN_PASSWORD}

# Forgejo Database Password
FORGEJO_DB_PASSWORD={FORGEJO_DB_PASSWORD}

# Forgejo Secret Key (for encryption)
FORGEJO_SECRET_KEY={FORGEJO_SECRET_KEY}

# Forgejo Internal Token (for API)
FORGEJO_INTERNAL_TOKEN={FORGEJO_INTERNAL_TOKEN}

# Monitoring Addon Secrets
GRAFANA_ADMIN_PASSWORD={GRAFANA_ADMIN_PASSWORD}

# Grafana SMTP Password (optional - for email alerts)
# Set this manually if you enable SMTP in config.yml
# GRAFANA_SMTP_PASSWORD=your-smtp-password-here
""".format(**project_secrets)

        with open(env_file, "w") as f:
            f.write(env_content)

        # Set restrictive permissions (owner read/write only)
        env_file.chmod(0o600)

        console.print(
            "[green]✅ Orchestrator secrets saved to: shared/orchestrator/.env[/green]"
        )

    # Get GCP config from orchestrator.yml
    gcp_config = orch_config.config.get("gcp", {})
    ssh_config = orch_config.config.get("ssh", {})

    gcp_project_id = gcp_config.get("project_id")
    if not gcp_project_id:
        console.print("[red]❌ gcp.project_id not set in shared/orchestrator.yml[/red]")
        raise SystemExit(1)

    ssh_key_path = ssh_config.get("public_key_path", "~/.ssh/superdeploy_deploy.pub")

    console.print("\n[cyan]📋 Orchestrator Configuration:[/cyan]")
    vm_config = orch_config.get_vm_config()
    console.print(f"  GCP Project: {gcp_project_id}")
    console.print(f"  Region: {gcp_config.get('region')}")
    console.print(f"  Zone: {gcp_config.get('zone')}")
    console.print(f"  VM: {vm_config.get('name')}")
    console.print(f"  Machine Type: {vm_config.get('machine_type')}")
    console.print(f"  Disk Size: {vm_config.get('disk_size')}GB")

    # Terraform (skip if flag provided or already deployed)
    if skip_terraform or orch_config.is_deployed():
        console.print("\n[dim]☁️  Skipping Terraform (VM already exists)...[/dim]")
        orchestrator_ip = orch_config.get_ip()
        if not orchestrator_ip:
            console.print("[red]❌ No IP found! Run without --skip-terraform[/red]")
            raise SystemExit(1)
        console.print(f"[dim]✓ Using existing IP: {orchestrator_ip}[/dim]")
    else:
        console.print("\n[cyan]☁️  Provisioning VM (Terraform)...[/cyan]")

        import subprocess

        terraform_dir = shared_dir / "terraform"

        # Create workspace first (non-interactive)
        console.print("[dim]Creating workspace...[/dim]")
        result = subprocess.run(
            ["terraform", "workspace", "new", "orchestrator"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )
        # Ignore error if workspace already exists

        # Select workspace
        result = subprocess.run(
            ["terraform", "workspace", "select", "orchestrator"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]❌ Failed to select workspace: {result.stderr}[/red]")
            raise SystemExit(1)

        console.print("[dim]✓ Workspace: orchestrator[/dim]")

        # Now init
        terraform_init()

        # Generate tfvars
        tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)
        tfvars_file = shared_dir / "terraform" / "orchestrator.auto.tfvars.json"

        import json

        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        console.print(f"[dim]✓ Generated: {tfvars_file.name}[/dim]")

        # Apply
        terraform_apply(
            "orchestrator",
            None,
            var_file=str(tfvars_file),
            auto_approve=True,
            preserve_ip=preserve_ip,
        )

        console.print("[green]✅ VM provisioned![/green]")

        # Get IP
        outputs = get_terraform_outputs("orchestrator")
        vm_ips = outputs.get("vm_public_ips", {}).get("value", {})
        orchestrator_ip = vm_ips.get("main-0")

    if not orchestrator_ip:
        console.print("[red]❌ Failed to get orchestrator IP from Terraform[/red]")
        raise SystemExit(1)

    console.print(f"[green]✅ Orchestrator IP: {orchestrator_ip}[/green]")

    # Wait for SSH to be ready
    console.print("\n[yellow]⏳ Waiting for SSH to be ready...[/yellow]")
    import time
    import subprocess

    ssh_key = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
    ssh_user = ssh_config.get("user", "superdeploy")

    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{orchestrator_ip} 'echo ready'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                console.print(f"[green]✅ SSH ready after {attempt * 10}s[/green]")
                break
        except:
            pass

        if attempt < max_attempts:
            console.print(f"[dim]Attempt {attempt}/{max_attempts}... waiting 10s[/dim]")
            time.sleep(10)
        else:
            console.print("[yellow]⚠️  SSH not ready yet, continuing anyway...[/yellow]")
            break

    # Ansible
    console.print("\n[cyan]⚙️  Configuring Forgejo (Ansible)...[/cyan]")

    ansible_dir = shared_dir / "ansible"

    # Generate inventory
    inventory_content = f"""[orchestrator]
orchestrator ansible_host={orchestrator_ip} ansible_user=superdeploy
"""
    inventory_path = ansible_dir / "inventories" / "orchestrator.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)

    console.print(f"[dim]✓ Generated: {inventory_path.name}[/dim]")

    # Get Ansible vars
    ansible_vars = orch_config.to_ansible_vars()

    # IMPORTANT: Manually set project_secrets for orchestrator
    # (generate_ansible_extra_vars looks in projects/{name}/.env but orchestrator is in shared/orchestrator/.env)
    ansible_vars["project_secrets"] = project_secrets

    # Add preserve_ip flag to Ansible vars if set
    if preserve_ip:
        ansible_vars["preserve_ip"] = True
        console.print(
            "[yellow]⚠️  IP preservation enabled - static IP will be kept on destroy[/yellow]"
        )

    # Discover all projects for monitoring
    projects_dir = project_root / "projects"
    project_targets = []
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir() and (project_dir / ".env").exists():
                from dotenv import dotenv_values

                env_vars = dotenv_values(project_dir / ".env")
                # Collect all external IPs for this project
                for key, value in env_vars.items():
                    if key.endswith("_EXTERNAL_IP") and value:
                        # Add Caddy metrics endpoint (port 2019)
                        project_targets.append(f"{value}:2019")

    ansible_vars["project_targets"] = project_targets

    # Handle --addon flag (selective addon deployment)
    if addon:
        addon_list = [a.strip() for a in addon.split(",")]
        console.print(f"\n[yellow]📦 Deploying only: {', '.join(addon_list)}[/yellow]")
        # Override enabled_addons directly (simpler than using addon_filter)
        ansible_vars["enabled_addons"] = addon_list
        # Auto-set tags to addons only if not specified
        if not tags:
            tags = "addons"

    # Use custom tags if provided, otherwise run all phases
    ansible_tags = tags if tags else "foundation,addons"

    # Display resume point if provided
    if start_at_task:
        console.print(f"\n[yellow]⏩ Resuming from task: '{start_at_task}'[/yellow]")
        console.print("[dim]Skipping all tasks before this point[/dim]\n")

    # Build Ansible command
    ansible_cmd = build_ansible_command(
        ansible_dir=ansible_dir,
        project_root=project_root,
        project_config=ansible_vars,
        env_vars=project_secrets,  # Pass secrets as env vars
        tags=ansible_tags,
        project_name="orchestrator",
        start_at_task=start_at_task,
    )

    run_command(ansible_cmd)

    console.print("[green]✅ Forgejo configured![/green]")

    # Create Forgejo PAT
    console.print("\n[cyan]🔑 Creating Forgejo PAT...[/cyan]")

    import urllib.parse
    import time
    import requests

    forgejo_config = orch_config.get_forgejo_config()
    admin_user = forgejo_config.get("admin_user")
    admin_password = project_secrets.get("FORGEJO_ADMIN_PASSWORD")
    org = forgejo_config.get("org")
    repo = forgejo_config.get("repo")
    port = forgejo_config.get("port", 3001)

    # Wait for Forgejo API to be ready
    console.print(f"[dim]Waiting for Forgejo API at {orchestrator_ip}:{port}...[/dim]")
    forgejo_url = f"http://{orchestrator_ip}:{port}"
    api_ready = False
    for attempt in range(12):  # 12 attempts = 60 seconds max
        try:
            console.print(
                f"[dim]Attempt {attempt + 1}/12: Checking {forgejo_url}/api/v1/version[/dim]"
            )
            response = requests.get(f"{forgejo_url}/api/v1/version", timeout=3)
            console.print(f"[dim]Response: {response.status_code}[/dim]")
            if response.status_code == 200:
                console.print("[dim]✓ Forgejo API is ready[/dim]")
                api_ready = True
                break
        except Exception as e:
            console.print(f"[dim]Error: {str(e)[:100]}[/dim]")

        if attempt < 11:
            time.sleep(5)

    if not api_ready:
        console.print("[yellow]⚠️  Forgejo API not ready after 60 seconds[/yellow]")
        console.print(
            "[yellow]   Skipping PAT creation - you can create it manually later[/yellow]"
        )
        forgejo_pat = None

    # Create PAT (only if API is ready)
    if api_ready:
        token_name = f"superdeploy-pat-{int(time.time())}"
        try:
            response = requests.post(
                f"{forgejo_url}/api/v1/users/{admin_user}/tokens",
                auth=(admin_user, admin_password),
                json={
                    "name": token_name,
                    "scopes": [
                        "write:activitypub",
                        "write:admin",
                        "write:issue",
                        "write:misc",
                        "write:notification",
                        "write:organization",
                        "write:package",
                        "write:repository",
                        "write:user",
                    ],
                },
                timeout=10,
            )

            if response.status_code == 201:
                forgejo_pat = response.json()["sha1"]
                console.print("[green]✅ Forgejo PAT created[/green]")

                # Save PAT to orchestrator .env
                env_file = shared_dir / "orchestrator" / ".env"
                with open(env_file, "r") as f:
                    lines = f.readlines()

                # Add or update FORGEJO_PAT
                pat_found = False
                for i, line in enumerate(lines):
                    if line.startswith("FORGEJO_PAT="):
                        lines[i] = f"FORGEJO_PAT={forgejo_pat}\n"
                        pat_found = True
                        break

                if not pat_found:
                    # Just add PAT
                    lines.append("\n# Forgejo Personal Access Token\n")
                    lines.append(f"FORGEJO_PAT={forgejo_pat}\n")

                with open(env_file, "w") as f:
                    f.writelines(lines)

                console.print("[green]✅ PAT saved to shared/orchestrator/.env[/green]")
            else:
                console.print(
                    f"[yellow]⚠️  PAT creation failed: {response.text}[/yellow]"
                )
                forgejo_pat = None
        except Exception as e:
            console.print(f"[yellow]⚠️  PAT creation failed: {e}[/yellow]")
            forgejo_pat = None
    else:
        forgejo_pat = None

    # Push superdeploy repo to Forgejo
    console.print("\n[cyan]📤 Pushing superdeploy repo to Forgejo...[/cyan]")

    # Wait for Forgejo to be fully ready
    console.print("[dim]Waiting for Forgejo to be ready...[/dim]")
    forgejo_ready = False
    for attempt in range(30):
        try:
            result = subprocess.run(
                f"curl -sSf -m 3 http://{orchestrator_ip}:{port}/ >/dev/null 2>&1",
                shell=True,
                capture_output=True,
            )
            if result.returncode == 0:
                console.print("[dim]✓ Forgejo is ready[/dim]")
                forgejo_ready = True
                break
        except:
            pass
        if attempt < 29:
            time.sleep(5)

    if not forgejo_ready:
        console.print(
            "[yellow]⚠️  Forgejo not ready after 150 seconds, continuing anyway...[/yellow]"
        )

    # Build Forgejo URL with credentials
    encoded_pass = urllib.parse.quote(admin_password)
    forgejo_url = (
        f"http://{admin_user}:{encoded_pass}@{orchestrator_ip}:{port}/{org}/{repo}.git"
    )

    # Remove old forgejo remote if exists
    subprocess.run(
        ["git", "remote", "remove", "forgejo"],
        cwd=str(project_root),
        capture_output=True,
    )

    # Add new forgejo remote
    result = subprocess.run(
        ["git", "remote", "add", "forgejo", forgejo_url],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(
            f"[yellow]⚠️  Failed to add forgejo remote: {result.stderr}[/yellow]"
        )
    else:
        # Push to forgejo
        result = subprocess.run(
            ["git", "push", "forgejo", "master:master", "-f"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            console.print("[green]✅ Superdeploy repo pushed to Forgejo![/green]")
        else:
            console.print(f"[yellow]⚠️  Git push failed: {result.stderr}[/yellow]")

    # Mark as deployed
    orch_config.mark_deployed(orchestrator_ip)

    console.print("\n[green]✅ Orchestrator deployed successfully![/green]")
    console.print(f"\n[bold]Forgejo URL:[/bold] http://{orchestrator_ip}:3001")
    console.print(f"[bold]Admin User:[/bold] {admin_user}")
    console.print(f"[bold]Admin Password:[/bold] {admin_password}")
    console.print(
        f"[bold]Repository:[/bold] http://{orchestrator_ip}:{port}/{org}/{repo}"
    )
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("1. Deploy your projects: superdeploy up -p <project>")


@orchestrator.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--preserve-ip", is_flag=True, help="Keep static IP (don't delete)")
def down(yes, preserve_ip):
    """Destroy orchestrator VM and clean up state"""
    from rich.prompt import Confirm

    console.print(
        Panel.fit(
            "[bold red]⚠️  Orchestrator Destruction[/bold red]\n\n"
            "[white]This will destroy the orchestrator VM and clean up all state[/white]",
            border_style="red",
        )
    )

    if not yes:
        confirmed = Confirm.ask(
            "[bold red]Are you sure you want to destroy orchestrator?[/bold red]",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]❌ Cancelled[/yellow]")
            return

    project_root = get_project_root()
    shared_dir = project_root / "shared"

    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    console.print("\n[cyan]🔥 Destroying orchestrator...[/cyan]")

    import subprocess

    # Use Terraform destroy (same as superdeploy down)
    console.print("\n[cyan]🔥 Running terraform destroy...[/cyan]")

    terraform_success = False

    # Check if workspace exists
    from cli.terraform_utils import workspace_exists

    terraform_init()

    if not workspace_exists("orchestrator"):
        console.print(
            "[dim]✓ No Terraform workspace found, skipping terraform destroy[/dim]"
        )
        terraform_success = True
    else:
        try:
            select_workspace("orchestrator", create=False)

            # Generate tfvars for destroy
            gcp_config = orch_config.config.get("gcp", {})
            ssh_config = orch_config.config.get("ssh", {})
            gcp_project_id = gcp_config.get("project_id")
            ssh_key_path = ssh_config.get(
                "public_key_path", "~/.ssh/superdeploy_deploy.pub"
            )

            tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)
            tfvars_file = shared_dir / "terraform" / "orchestrator.auto.tfvars.json"

            import json

            with open(tfvars_file, "w") as f:
                json.dump(tfvars, f, indent=2)

            # Run destroy
            terraform_dir = shared_dir / "terraform"
            result = subprocess.run(
                ["terraform", "destroy", f"-var-file={tfvars_file}", "-auto-approve"],
                cwd=terraform_dir,
                capture_output=False,
                text=True,
            )

            if result.returncode == 0:
                console.print("[green]✅ Terraform destroy successful[/green]")
                terraform_success = True
            else:
                console.print(
                    "[yellow]⚠️  Terraform destroy had issues, cleaning manually...[/yellow]"
                )

        except Exception as e:
            console.print(f"[yellow]⚠️  Terraform destroy error: {e}[/yellow]")
            console.print("[yellow]Cleaning manually...[/yellow]")

    # Manual cleanup with gcloud (always run to ensure everything is gone)
    console.print("\n[cyan]🧹 Manual cleanup with gcloud...[/cyan]")

    gcp_config = orch_config.config.get("gcp", {})
    zone = gcp_config.get("zone", "us-central1-a")
    region = gcp_config.get("region", "us-central1")

    # Always try to clean up, even if terraform succeeded
    if True:
        console.print("\n[cyan]🧹 Manual cleanup with gcloud...[/cyan]")

        gcp_config = orch_config.config.get("gcp", {})
        zone = gcp_config.get("zone", "us-central1-a")
        region = gcp_config.get("region", "us-central1")

        # Delete VM
        console.print("[dim]Deleting VM orchestrator-main-0...[/dim]")
        result = subprocess.run(
            f"gcloud compute instances delete orchestrator-main-0 --zone={zone} --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]  ✓ VM deleted[/green]")
        elif (
            "not found" in result.stderr.lower()
            or "could not fetch resource" in result.stderr.lower()
        ):
            console.print("[dim]  ✓ VM not found (already deleted)[/dim]")
        else:
            console.print(
                f"[yellow]  ⚠ VM deletion: {result.stderr.strip()[:100]}[/yellow]"
            )

        # Delete External IP (unless --preserve-ip flag is set)
        if preserve_ip:
            console.print(
                "[yellow]  ⊙ External IP preserved (--preserve-ip flag)[/yellow]"
            )
        else:
            console.print("[dim]Deleting External IP orchestrator-main-0-ip...[/dim]")
            result = subprocess.run(
                f"gcloud compute addresses delete orchestrator-main-0-ip --region={region} --quiet",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print("[green]  ✓ External IP deleted[/green]")
            elif (
                "not found" in result.stderr.lower()
                or "could not fetch resource" in result.stderr.lower()
            ):
                console.print("[dim]  ✓ External IP not found (already deleted)[/dim]")
            else:
                console.print(
                    f"[yellow]  ⚠ External IP deletion: {result.stderr.strip()[:100]}[/yellow]"
                )

        # Delete Firewall Rules (all network rules)
        console.print("[dim]Deleting Firewall Rules...[/dim]")
        result = subprocess.run(
            "gcloud compute firewall-rules list --filter='network:superdeploy-network' --format='value(name)'",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            firewall_rules = result.stdout.strip().split("\n")
            for rule in firewall_rules:
                rule = rule.strip()
                if rule:
                    result = subprocess.run(
                        f"gcloud compute firewall-rules delete {rule} --quiet",
                        shell=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        console.print(f"[green]  ✓ {rule} deleted[/green]")
                    else:
                        console.print(f"[yellow]  ⚠ {rule} deletion failed[/yellow]")
        else:
            console.print("[dim]  ✓ No firewall rules found[/dim]")

        # Delete Subnet
        console.print("[dim]Deleting Subnet superdeploy-network-subnet...[/dim]")
        result = subprocess.run(
            f"gcloud compute networks subnets delete superdeploy-network-subnet --region={region} --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]  ✓ Subnet deleted[/green]")
        elif (
            "not found" in result.stderr.lower()
            or "could not fetch resource" in result.stderr.lower()
        ):
            console.print("[dim]  ✓ Subnet not found (already deleted)[/dim]")
        else:
            console.print(
                f"[yellow]  ⚠ Subnet deletion: {result.stderr.strip()[:100]}[/yellow]"
            )

        # Delete Network
        console.print("[dim]Deleting Network superdeploy-network...[/dim]")
        result = subprocess.run(
            "gcloud compute networks delete superdeploy-network --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]  ✓ Network deleted[/green]")
        elif (
            "not found" in result.stderr.lower()
            or "could not fetch resource" in result.stderr.lower()
        ):
            console.print("[dim]  ✓ Network not found (already deleted)[/dim]")
        else:
            console.print(
                f"[yellow]  ⚠ Network deletion: {result.stderr.strip()[:100]}[/yellow]"
            )

        console.print("[green]✅ Manual cleanup complete[/green]")

    # 2. Clean Terraform state
    terraform_state_dir = (
        shared_dir / "terraform" / "terraform.tfstate.d" / "orchestrator"
    )
    if terraform_state_dir.exists():
        import shutil

        shutil.rmtree(terraform_state_dir)
        console.print("[green]✅ Terraform state cleaned[/green]")

    # 3. Clean .env (remove ORCHESTRATOR_IP)
    env_path = shared_dir / "orchestrator" / ".env"
    if env_path.exists():
        env_lines = []
        with open(env_path, 'r') as f:
            for line in f:
                if not line.strip().startswith('ORCHESTRATOR_IP='):
                    env_lines.append(line)
        
        with open(env_path, 'w') as f:
            f.writelines(env_lines)
        
        console.print("[green]✅ .env cleaned (ORCHESTRATOR_IP removed)[/green]")
    else:
        console.print("[dim]✓ .env not found (already clean)[/dim]")

    # 4. Clean inventory
    inventory_file = shared_dir / "ansible" / "inventories" / "orchestrator.ini"
    if inventory_file.exists():
        inventory_file.unlink()
        console.print("[green]✅ Inventory cleaned[/green]")

    console.print("\n[green]✅ Orchestrator destroyed and cleaned up![/green]")


@orchestrator.command()
def status():
    """Show orchestrator status"""
    project_root = get_project_root()
    shared_dir = project_root / "shared"

    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    if orch_config.is_deployed():
        console.print("[green]✅ Orchestrator is deployed[/green]")
        console.print(f"  IP: {orch_config.get_ip()}")
        console.print(f"  URL: http://{orch_config.get_ip()}:3001")
        console.print(
            f"  Last Updated: {orch_config.config.get('state', {}).get('last_updated', 'Unknown')}"
        )
    else:
        console.print("[yellow]⚠️  Orchestrator not deployed[/yellow]")
        console.print("  Run: superdeploy orchestrator up")


if __name__ == "__main__":
    orchestrator()
