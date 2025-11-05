"""SuperDeploy CLI - Orchestrator command (with improved logging and UX)"""

import click
import subprocess
import time
from rich.console import Console
from cli.ui_components import show_header
from rich.prompt import Prompt, Confirm
from cli.utils import get_project_root
from cli.logger import DeployLogger, run_with_progress

console = Console()


@click.command(name="orchestrator:init")
def orchestrator_init():
    """Initialize orchestrator configuration (interactive wizard)"""

    show_header(
        title="Orchestrator Setup",
        subtitle="Configure global orchestrator (Forgejo + Monitoring)",
        show_logo=True,
        console=console,
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
            default=False,
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

    gcp_project = Prompt.ask("  [cyan]GCP Project ID[/cyan]", default="")

    region = Prompt.ask("  [cyan]GCP Region[/cyan]", default="us-central1")

    zone = Prompt.ask("  [cyan]GCP Zone[/cyan]", default=f"{region}-a")

    console.print("\n[bold cyan]🔐 SSL Configuration[/bold cyan]")
    console.print("[dim]Email for Let's Encrypt SSL certificates[/dim]\n")

    ssl_email = Prompt.ask("  [cyan]SSL Email[/cyan]", default="")

    console.print("\n[bold cyan]🔧 Forgejo Configuration[/bold cyan]")
    console.print("[dim]Git server with CI/CD capabilities[/dim]\n")

    admin_user = Prompt.ask("  [cyan]Admin Username[/cyan]", default="admin")

    admin_email = Prompt.ask("  [cyan]Admin Email[/cyan]", default="")

    org = Prompt.ask("  [cyan]Organization Name[/cyan]", default="")

    console.print("\n[bold cyan]📊 Global Monitoring Configuration[/bold cyan]")
    console.print("[dim]Grafana and Prometheus will monitor ALL projects[/dim]")
    console.print(
        "[dim]Optional: Enable HTTPS with custom domains (e.g., grafana.cfk.com)[/dim]\n"
    )

    enable_domains = Confirm.ask(
        "  [cyan]Configure custom domains?[/cyan]", default=False
    )

    grafana_domain = ""
    prometheus_domain = ""
    forgejo_domain = ""
    enable_caddy = False

    if enable_domains:
        grafana_domain = Prompt.ask(
            "  [cyan]Grafana Domain[/cyan] (global monitoring for all projects)",
            default="",
        )
        prometheus_domain = Prompt.ask(
            "  [cyan]Prometheus Domain[/cyan] (global metrics for all projects)",
            default="",
        )
        forgejo_domain = Prompt.ask(
            "  [cyan]Forgejo Domain[/cyan] (git server for all projects)", default=""
        )
        enable_caddy = True

    # Read template
    with open(template_path, "r") as f:
        config_content = f.read()

    # Replace placeholders
    config_content = config_content.replace("YOUR_GCP_PROJECT_ID", gcp_project)
    config_content = config_content.replace(
        'region: "us-central1"', f'region: "{region}"'
    )
    config_content = config_content.replace('zone: "us-central1-a"', f'zone: "{zone}"')
    config_content = config_content.replace(
        'ssl_email: ""', f'ssl_email: "{ssl_email}"'
    )
    config_content = config_content.replace("YOUR_USERNAME", admin_user)
    config_content = config_content.replace("YOUR_EMAIL@example.com", admin_email)
    config_content = config_content.replace("YOUR_ORG", org)

    # Update domains if configured
    if enable_domains:
        config_content = config_content.replace(
            'grafana:\n  domain: ""', f'grafana:\n  domain: "{grafana_domain}"'
        )
        config_content = config_content.replace(
            'prometheus:\n  domain: ""', f'prometheus:\n  domain: "{prometheus_domain}"'
        )
        config_content = config_content.replace(
            'forgejo:\n  domain: ""', f'forgejo:\n  domain: "{forgejo_domain}"'
        )
        config_content = config_content.replace(
            "enabled: false  # Set to true", "enabled: true  # Set to true"
        )

    # Update header
    config_content = config_content.replace(
        "# Orchestrator Configuration Template", "# Orchestrator Configuration"
    )
    config_content = config_content.replace(
        "# Copy this to config.yml and customize for your setup",
        "# Auto-generated by: superdeploy orchestrator init",
    )

    # Allocate Docker subnet for orchestrator
    console.print("\n[dim]Allocating network subnet...[/dim]")
    from cli.subnet_allocator import SubnetAllocator

    allocator = SubnetAllocator()

    # Check if orchestrator already has a subnet allocated
    if "orchestrator" not in allocator.docker_allocations:
        # Allocate and save to file
        docker_subnet = SubnetAllocator.ORCHESTRATOR_DOCKER_SUBNET
        allocator.docker_allocations["orchestrator"] = docker_subnet
        allocator.allocations["docker_subnets"] = allocator.docker_allocations
        allocator._save_allocations()
    else:
        docker_subnet = allocator.docker_allocations["orchestrator"]

    # Add docker_subnet line to network section (preserve formatting)
    lines = config_content.split("\n")
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Add docker_subnet after subnet_cidr line
        if "subnet_cidr:" in line and "docker_subnet" not in config_content:
            # Get the indentation from current line
            indent = len(line) - len(line.lstrip())
            new_lines.append(
                f'{" " * indent}docker_subnet: "{docker_subnet}"  # Reserved for orchestrator'
            )

    config_content = "\n".join(new_lines)
    console.print(f"[dim]✓ Docker subnet allocated: {docker_subnet}[/dim]")

    # Write config
    with open(config_path, "w") as f:
        f.write(config_content)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[color(248)]Orchestrator configured.[/color(248)]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(f"\n[cyan]📄 Config saved to:[/cyan] {config_path}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. [dim]Review config:[/dim] shared/orchestrator/config.yml")
    console.print(
        "  2. [dim]Deploy orchestrator:[/dim] [cyan]superdeploy orchestrator up[/cyan]"
    )

    if enable_domains:
        console.print("\n[yellow]⚠️  Don't forget to:[/yellow]")
        console.print("  • Point DNS A records to orchestrator IP")
        console.print("  • Wait for DNS propagation before deployment")

    console.print()


@click.command(name="orchestrator:down")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--preserve-ip", is_flag=True, help="Keep static IP (don't delete)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def orchestrator_down(yes, preserve_ip, verbose):
    """Destroy orchestrator VM and clean up state"""

    project_root = get_project_root()

    # Initialize logger
    logger = DeployLogger("orchestrator", "down", verbose=verbose)

    if not verbose:
        show_header(
            title="Orchestrator Destruction",
            subtitle="This will destroy the orchestrator VM and clean up all state!",
            border_color="red",
            console=console,
        )

    if not yes:
        confirmed = Confirm.ask(
            "\nAre you ABSOLUTELY SURE you want to destroy the orchestrator?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Cancelled. Orchestrator preserved.[/dim]")
            logger.log("User cancelled destruction")
            return

    logger.step("[1/3] Preparing Destruction")

    shared_dir = project_root / "shared"

    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        logger.log_error(str(e))
        raise SystemExit(1)

    console.print("  [dim]✓ Configuration loaded[/dim]")

    import subprocess
    from cli.terraform_utils import (
        workspace_exists,
        terraform_init,
        select_workspace,
    )

    terraform_success = False
    terraform_dir = shared_dir / "terraform"

    # Check workspace before init
    if not workspace_exists("orchestrator"):
        console.print(
            "  [green]✓[/green] [dim]No workspace found (already destroyed)[/dim]"
        )
        terraform_success = True
    else:
        logger.step("[2/3] Terraform Destroy")

        # Switch to default workspace before init to avoid prompts
        subprocess.run(
            "terraform workspace select default 2>/dev/null || true",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
        )

        terraform_init(quiet=True)
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
            destroy_cmd = f"cd {terraform_dir} && terraform destroy -var-file={tfvars_file} -auto-approve -no-color"

            returncode, stdout, stderr = run_with_progress(
                logger,
                destroy_cmd,
                "Destroying infrastructure (this may take 2-3 minutes)",
                cwd=project_root,
            )

            if returncode == 0:
                console.print("  [dim]✓ All resources destroyed[/dim]")
                terraform_success = True
            else:
                logger.warning("Terraform destroy failed, attempting manual cleanup")
                console.print("  ⚠ Partial destruction")
                terraform_success = False

        except Exception as e:
            logger.warning(f"Terraform error: {e}")
            console.print("  ⚠ Partial destruction")
            terraform_success = False

    # Manual cleanup with gcloud (only if terraform failed)
    if not terraform_success:
        logger.step("[3/3] Manual Cleanup")

        gcp_config = orch_config.config.get("gcp", {})
        zone = gcp_config.get("zone", "us-central1-a")
        region = gcp_config.get("region", "us-central1")

        vms_deleted = 0
        ips_deleted = 0

        # Delete VM
        result = subprocess.run(
            f"gcloud compute instances delete orchestrator-main-0 --zone={zone} --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            vms_deleted += 1

        # Delete External IP (unless --preserve-ip flag is set)
        if not preserve_ip:
            result = subprocess.run(
                f"gcloud compute addresses delete orchestrator-main-0-ip --region={region} --quiet",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 or "not found" in result.stderr.lower():
                ips_deleted += 1

        firewalls_deleted = 0
        subnets_deleted = 0
        networks_deleted = 0

        # Delete Firewall Rules (all network rules)
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
                        firewalls_deleted += 1

        # Delete Subnet
        result = subprocess.run(
            f"gcloud compute networks subnets delete superdeploy-network-subnet --region={region} --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "not found" in result.stderr.lower():
            subnets_deleted += 1

        # Delete Network
        result = subprocess.run(
            "gcloud compute networks delete superdeploy-network --quiet",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            networks_deleted += 1

        # Show summary
        resources = []
        if vms_deleted > 0:
            resources.append(f"{vms_deleted} VM(s)")
        if firewalls_deleted > 0:
            resources.append(f"{firewalls_deleted} firewall rule(s)")
        if subnets_deleted > 0:
            resources.append(f"{subnets_deleted} subnet(s)")
        if networks_deleted > 0:
            resources.append(f"{networks_deleted} network(s)")
        if ips_deleted > 0:
            resources.append(f"{ips_deleted} IP(s)")

        if resources:
            console.print(
                f"  [dim]✓ GCP resources cleaned: {', '.join(resources)}[/dim]"
            )
        else:
            console.print("  [dim]✓ No GCP resources found[/dim]")

    # Clean Terraform state
    terraform_state_dir = (
        shared_dir / "terraform" / "terraform.tfstate.d" / "orchestrator"
    )
    if terraform_state_dir.exists():
        import shutil

        shutil.rmtree(terraform_state_dir)

    # Clean .env (remove ORCHESTRATOR_IP)
    env_path = shared_dir / "orchestrator" / ".env"
    if env_path.exists():
        env_lines = []
        with open(env_path, "r") as f:
            for line in f:
                if not line.strip().startswith("ORCHESTRATOR_IP="):
                    env_lines.append(line)

        with open(env_path, "w") as f:
            f.writelines(env_lines)

    # Clean inventory
    inventory_file = shared_dir / "ansible" / "inventories" / "orchestrator.ini"
    if inventory_file.exists():
        inventory_file.unlink()

    # Release subnet allocation
    try:
        from cli.subnet_allocator import SubnetAllocator

        allocator = SubnetAllocator()
        allocator.release_subnet("orchestrator")
    except Exception as e:
        logger.warning(f"Subnet release warning: {e}")

    console.print("  [dim]✓ Local files cleaned[/dim]")

    console.print("\n[color(248)]Orchestrator destroyed.[/color(248)]")


@click.command(name="orchestrator:status")
def orchestrator_status():
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


@click.command(name="orchestrator:up")
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
    "--verbose",
    "-v",
    is_flag=True,
    help="Show all command output (default: clean UI with logs)",
)
def orchestrator_up(skip_terraform, preserve_ip, addon, tags, verbose):
    """Deploy orchestrator VM with Forgejo (runs Terraform + Ansible by default)"""

    if not verbose:
        show_header(
            title="Orchestrator Deployment",
            subtitle="Deploying shared Forgejo instance + Monitoring for all projects",
            show_logo=True,
            console=console,
        )

    project_root = get_project_root()
    shared_dir = project_root / "shared"

    # Initialize logger
    with DeployLogger("orchestrator", "up", verbose=verbose) as logger:
        try:
            _deploy_orchestrator_v2(
                logger,
                project_root,
                shared_dir,
                skip_terraform,
                preserve_ip,
                addon,
                tags,
                verbose,
            )

            if not verbose:
                console.print(
                    "\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]"
                )
                console.print("[color(248)]Orchestrator deployed.[/color(248)]")
                console.print(
                    "[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]\n"
                )

        except Exception as e:
            logger.log_error(str(e), context="Orchestrator deployment failed")
            raise SystemExit(1)


def _deploy_orchestrator_v2(
    logger,
    project_root,
    shared_dir,
    skip_terraform,
    preserve_ip,
    addon,
    tags,
    verbose,
):
    """Internal function for orchestrator deployment with logging"""

    logger.step("[1/3] Setup & Infrastructure")

    # Load orchestrator config
    logger.log("Loading configuration...")
    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
        logger.log("✓ Configuration loaded")
    except FileNotFoundError as e:
        logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Generate and save secrets
    logger.log("Checking secrets...")
    import secrets as secrets_module

    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    env_file = orchestrator_dir / ".env"

    if env_file.exists():
        logger.log("✓ Secrets verified")
    else:
        logger.log("Generating new secrets")
        project_secrets = {
            "FORGEJO_ADMIN_PASSWORD": secrets_module.token_urlsafe(32),
            "FORGEJO_DB_PASSWORD": secrets_module.token_urlsafe(32),
            "FORGEJO_SECRET_KEY": secrets_module.token_urlsafe(48),
            "FORGEJO_INTERNAL_TOKEN": secrets_module.token_urlsafe(79),
            "GRAFANA_ADMIN_PASSWORD": secrets_module.token_urlsafe(32),
        }

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

        env_file.chmod(0o600)
        logger.log("✓ Secrets generated")

    # Get GCP config
    gcp_config = orch_config.config.get("gcp", {})
    ssh_config = orch_config.config.get("ssh", {})

    gcp_project_id = gcp_config.get("project_id")
    if not gcp_project_id:
        logger.log_error("gcp.project_id not set in shared/orchestrator/config.yml")
        raise SystemExit(1)

    ssh_key_path = ssh_config.get("public_key_path", "~/.ssh/superdeploy_deploy.pub")

    # Terraform
    if not skip_terraform:
        logger.log("Provisioning VM (2-3 min)...")

        # First ensure we're on default workspace, then init
        logger.log("Ensuring default workspace")
        terraform_dir = shared_dir / "terraform"

        # Check if .terraform directory exists
        terraform_state_dir = terraform_dir / ".terraform"
        if terraform_state_dir.exists():
            # Try to switch to default workspace before init
            subprocess.run(
                "terraform workspace select default 2>/dev/null || true",
                shell=True,
                cwd=terraform_dir,
                capture_output=True,
            )

        # Init silently
        from cli.terraform_utils import terraform_init

        try:
            terraform_init(quiet=True)
            logger.log("Terraform initialized")
        except Exception as e:
            logger.log_error("Terraform init failed", context=str(e))
            raise SystemExit(1)

        # Select or create orchestrator workspace (silently)
        from cli.terraform_utils import select_workspace

        try:
            select_workspace("orchestrator", create=True)
            logger.log("Workspace ready: orchestrator")
        except Exception as e:
            logger.log_error("Workspace setup failed", context=str(e))
            raise SystemExit(1)

        # Generate tfvars
        logger.log("Generating terraform variables")
        tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)

        tfvars_file = (
            project_root / "shared" / "terraform" / "orchestrator.auto.tfvars.json"
        )
        import json

        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        logger.log(f"Terraform vars saved to: {tfvars_file}")

        # Apply
        logger.log("Running terraform apply")
        apply_cmd = "cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings"

        if preserve_ip:
            logger.log("Preserve IP mode enabled")

        returncode, stdout, stderr = run_with_progress(
            logger,
            apply_cmd,
            "Provisioning infrastructure (this may take 2-3 minutes)",
            cwd=project_root,
        )

        if returncode != 0:
            logger.log_error("Terraform apply failed", context=stderr)
            raise SystemExit(1)

        console.print("  [dim]✓ VM provisioned[/dim]")

        # Get outputs
        # Ensure we're in orchestrator workspace
        try:
            select_workspace("orchestrator", create=False)
        except Exception as e:
            logger.log_error("Failed to select orchestrator workspace", context=str(e))
            raise SystemExit(1)

        # Get outputs from orchestrator workspace
        terraform_dir = shared_dir / "terraform"
        result = subprocess.run(
            "terraform output -json -no-color",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.log_error("Failed to get terraform outputs", context=result.stderr)
            raise SystemExit(1)

        import json

        outputs = json.loads(result.stdout)

        orchestrator_ip = (
            outputs.get("vm_public_ips", {}).get("value", {}).get("main-0")
        )

        if not orchestrator_ip:
            logger.log_error("Could not find orchestrator IP in terraform outputs")
            logger.log(f"Available outputs: {outputs}")
            raise SystemExit(1)

        # Save IP to .env
        orch_config.mark_deployed(orchestrator_ip)

        # Wait for SSH
        logger.log("Waiting for SSH...")
        ssh_key = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")

        max_attempts = 18
        for attempt in range(1, max_attempts + 1):
            logger.log(f"SSH check attempt {attempt}/{max_attempts}")

            check_cmd = f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{orchestrator_ip} 'sudo -n whoami' 2>&1"
            result = subprocess.run(
                check_cmd, shell=True, capture_output=True, text=True, timeout=10
            )

            logger.log_output(result.stdout, "stdout")
            logger.log_output(result.stderr, "stderr")

            if result.returncode == 0 and "root" in result.stdout:
                console.print("  [dim]✓ VM ready[/dim]")
                break

            if attempt < max_attempts:
                logger.log("VM not ready yet, waiting 10 seconds...")
                time.sleep(10)
        else:
            logger.warning("VM may not be fully ready, continuing anyway...")
            console.print("  [yellow]⚠[/yellow] [dim]VM partially ready[/dim]")

        # Clean SSH known_hosts
        subprocess.run(["ssh-keygen", "-R", orchestrator_ip], capture_output=True)

    else:
        orchestrator_ip = orch_config.get_ip()
        if not orchestrator_ip:
            logger.log_error("Orchestrator IP not found. Deploy with Terraform first.")
            raise SystemExit(1)

    # Create/Update Ansible inventory file (for both terraform and skip-terraform cases)
    inventory_dir = shared_dir / "ansible" / "inventories"
    inventory_dir.mkdir(parents=True, exist_ok=True)

    inventory_file = inventory_dir / "orchestrator.ini"
    ssh_user = ssh_config.get("user", "superdeploy")
    ssh_key = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")

    inventory_content = f"""[orchestrator]
orchestrator-main-0 ansible_host={orchestrator_ip} ansible_user={ssh_user} ansible_ssh_private_key_file={ssh_key} ansible_become=yes ansible_become_method=sudo

[all:vars]
ansible_python_interpreter=/usr/bin/python3
"""

    with open(inventory_file, "w") as f:
        f.write(inventory_content)

    # Phase 1 complete - show summary
    logger.success(f"Configuration • Secrets • VM @ {orchestrator_ip}")

    # Ansible - Phase 2 & 3
    logger.step("[2/3] Base System")

    from cli.ansible_utils import build_ansible_command

    ansible_dir = project_root / "shared" / "ansible"

    # Prepare ansible vars
    ansible_vars = orch_config.to_ansible_vars()

    # Load orchestrator secrets from .env
    from dotenv import dotenv_values

    orchestrator_secrets = {}
    env_file = shared_dir / "orchestrator" / ".env"
    if env_file.exists():
        orchestrator_secrets = dotenv_values(env_file)
        # Filter out non-secret values
        orchestrator_secrets = {
            k: v
            for k, v in orchestrator_secrets.items()
            if v and not k.startswith("#") and not k.startswith("ORCHESTRATOR_IP")
        }

    # Add secrets to ansible vars
    ansible_vars["project_secrets"] = orchestrator_secrets

    # Add orchestrator IP and ansible_host for runtime variables
    ansible_env_vars = {
        "superdeploy_root": str(project_root),
        "orchestrator_ip": orchestrator_ip,
        "ansible_host": orchestrator_ip,  # For addon env variables that use from_ansible
    }

    # Determine ansible tags and enabled addons
    if addon:
        # Deploy only specific addon(s)
        enabled_addons_list = [a.strip() for a in addon.split(",")]
        ansible_tags = "addons"  # Only run addons tag
        logger.log(f"Deploying only addon(s): {', '.join(enabled_addons_list)}")
    elif tags:
        ansible_tags = tags
        # For orchestrator, always deploy all addons unless specific ones requested
        enabled_addons_list = ["forgejo", "monitoring"]
    else:
        ansible_tags = "foundation,addons"
        # Deploy all orchestrator addons by default
        enabled_addons_list = ["forgejo", "monitoring"]

    logger.log(f"Running ansible with tags: {ansible_tags}")

    ansible_cmd = build_ansible_command(
        ansible_dir=ansible_dir,
        project_root=project_root,
        project_config=ansible_vars,
        env_vars=ansible_env_vars,
        tags=ansible_tags,
        project_name="orchestrator",
        ask_become_pass=False,
        enabled_addons=enabled_addons_list,
    )

    # Run ansible with clean tree view (no messy logs)
    from cli.ansible_runner import AnsibleRunner

    runner = AnsibleRunner(logger, title="Configuring Orchestrator", verbose=verbose)
    result_returncode = runner.run(ansible_cmd, cwd=project_root)

    if result_returncode != 0:
        logger.log_error(
            "Ansible configuration failed", context="Check logs for details"
        )
        raise SystemExit(1)

    console.print("[green]✓ Orchestrator configured[/green]")

    logger.success("Services configured successfully")

    # Display info and credentials (always show, regardless of verbose mode)
    from dotenv import dotenv_values

    env_file = shared_dir / "orchestrator" / ".env"
    secrets = dotenv_values(env_file) if env_file.exists() else {}

    forgejo_admin = orch_config.config.get("forgejo", {}).get("admin_user", "admin")
    forgejo_pass = secrets.get("FORGEJO_ADMIN_PASSWORD", "")
    grafana_pass = secrets.get("GRAFANA_ADMIN_PASSWORD", "")

    console.print("\n" + "━" * 60)
    console.print("[bold green]✅ Orchestrator Deployed![/bold green]")
    console.print("━" * 60)

    console.print(f"\n[cyan]📍 Orchestrator IP:[/cyan] {orchestrator_ip}")
    console.print("\n[bold cyan]🔐 Access Credentials:[/bold cyan]")
    console.print("\n[cyan]🌐 Forgejo (Git Server):[/cyan]")
    console.print(f"   URL: http://{orchestrator_ip}:3001")
    console.print(f"   Username: [bold]{forgejo_admin}[/bold]")
    console.print(f"   Password: [bold]{forgejo_pass}[/bold]")
    console.print("\n[cyan]📊 Grafana (Monitoring):[/cyan]")
    console.print(f"   URL: http://{orchestrator_ip}:3000")
    console.print("   Username: [bold]admin[/bold]")
    console.print(f"   Password: [bold]{grafana_pass}[/bold]")
    console.print("\n[cyan]📈 Prometheus (Metrics):[/cyan]")
    console.print(f"   URL: http://{orchestrator_ip}:9090")
    console.print("   [dim](No authentication required)[/dim]")

    console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
