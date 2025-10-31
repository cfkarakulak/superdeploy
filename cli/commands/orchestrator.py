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
    from cli.terraform_utils import (
        workspace_exists,
        terraform_init,
        select_workspace,
        terraform_apply,
        get_terraform_outputs,
    )

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
"""SuperDeploy CLI - Orchestrator command V2 (with improved logging and UX)"""

import click
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from cli.utils import get_project_root
from cli.logger import DeployLogger, run_with_progress

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
    help="Resume Ansible from a specific task (e.g. 'Install Docker')",
)
@click.option(
    "--verbose", "-v", is_flag=True, help="Show all command output (default: clean UI with logs)"
)
def up(skip_terraform, preserve_ip, addon, tags, start_at_task, verbose):
    """Deploy orchestrator VM with Forgejo (runs Terraform + Ansible by default)"""
    
    if not verbose:
        console.print(
            Panel.fit(
                "[bold cyan]🚀 Deploying Global Orchestrator[/bold cyan]\n\n"
                "[white]This will deploy a shared Forgejo instance for all projects[/white]",
                border_style="cyan",
            )
        )

    project_root = get_project_root()
    shared_dir = project_root / "shared"
    
    # Initialize logger
    with DeployLogger("orchestrator", "up", verbose=verbose) as logger:
        try:
            _deploy_orchestrator_v2(
                logger, project_root, shared_dir, skip_terraform, preserve_ip,
                addon, tags, start_at_task, verbose
            )
            
            if not verbose:
                console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
                console.print("[bold green]✅ Orchestrator Deployed![/bold green]")
                console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]\n")
                
        except Exception as e:
            logger.log_error(str(e), context="Orchestrator deployment failed")
            raise SystemExit(1)


def _deploy_orchestrator_v2(
    logger, project_root, shared_dir, skip_terraform, preserve_ip,
    addon, tags, start_at_task, verbose
):
    """Internal function for orchestrator deployment with logging"""
    
    # Load orchestrator config
    logger.step("Loading orchestrator configuration")
    from cli.core.orchestrator_loader import OrchestratorLoader
    
    orchestrator_loader = OrchestratorLoader(shared_dir)
    
    try:
        orch_config = orchestrator_loader.load()
        logger.success("Configuration loaded")
    except FileNotFoundError as e:
        logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)
    
    # Generate and save secrets
    logger.step("Checking secrets")
    import secrets as secrets_module
    
    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    
    env_file = orchestrator_dir / ".env"
    
    if env_file.exists():
        logger.success("Using existing secrets from .env")
        logger.log("Secrets file exists, skipping generation")
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
        logger.success("Secrets generated and saved")
    
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
        logger.step("Provisioning VM with Terraform")
        
        from cli.terraform_utils import (
            terraform_init,
            terraform_apply,
            select_workspace,
            get_terraform_outputs,
        )
        
        # Init
        logger.log("Running terraform init")
        returncode, stdout, stderr = run_with_progress(
            logger,
            "cd shared/terraform && terraform init -upgrade -no-color",
            "Initializing Terraform",
            cwd=project_root
        )
        
        if returncode != 0:
            logger.log_error("Terraform init failed", context=stderr)
            raise SystemExit(1)
        
        # Generate tfvars
        logger.log("Generating terraform variables")
        tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)
        
        tfvars_file = project_root / "shared" / "terraform" / "orchestrator.auto.tfvars.json"
        import json
        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        logger.log(f"Terraform vars saved to: {tfvars_file}")
        
        # Select workspace
        logger.log("Selecting terraform workspace: orchestrator")
        returncode, stdout, stderr = run_with_progress(
            logger,
            "cd shared/terraform && terraform workspace select orchestrator || terraform workspace new orchestrator",
            "Selecting workspace",
            cwd=project_root
        )
        
        if returncode != 0:
            logger.log_error("Workspace selection failed", context=stderr)
            raise SystemExit(1)
        
        # Apply
        logger.log("Running terraform apply")
        apply_cmd = f"cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings"
        
        if preserve_ip:
            logger.log("Preserve IP mode enabled")
        
        returncode, stdout, stderr = run_with_progress(
            logger,
            apply_cmd,
            "Provisioning infrastructure (this may take 2-3 minutes)",
            cwd=project_root
        )
        
        if returncode != 0:
            logger.log_error("Terraform apply failed", context=stderr)
            raise SystemExit(1)
        
        logger.success("VM provisioned successfully")
        
        # Get outputs
        logger.log("Extracting VM IP from terraform outputs")
        returncode, stdout, stderr = run_with_progress(
            logger,
            "cd shared/terraform && terraform output -json -no-color",
            "Getting VM details",
            cwd=project_root
        )
        
        if returncode != 0:
            logger.log_error("Failed to get terraform outputs", context=stderr)
            raise SystemExit(1)
        
        import json
        outputs = json.loads(stdout)
        orchestrator_ip = outputs.get("vm_public_ips", {}).get("value", {}).get("main-0")
        
        if not orchestrator_ip:
            logger.log_error("Could not find orchestrator IP in terraform outputs")
            raise SystemExit(1)
        
        logger.log(f"Orchestrator IP: {orchestrator_ip}")
        
        # Save IP to .env
        orch_config.mark_deployed(orchestrator_ip)
        logger.success(f"Orchestrator IP saved: {orchestrator_ip}")
        
        # Wait for SSH
        logger.step("Waiting for VM to be ready")
        ssh_key = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")
        
        max_attempts = 18
        for attempt in range(1, max_attempts + 1):
            logger.log(f"SSH check attempt {attempt}/{max_attempts}")
            
            check_cmd = f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{orchestrator_ip} 'sudo -n whoami' 2>&1"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            logger.log_output(result.stdout, "stdout")
            logger.log_output(result.stderr, "stderr")
            
            if result.returncode == 0 and "root" in result.stdout:
                logger.success("VM is ready and accessible")
                break
            
            if attempt < max_attempts:
                logger.log("VM not ready yet, waiting 10 seconds...")
                time.sleep(10)
        else:
            logger.warning("VM may not be fully ready, continuing anyway...")
        
        # Clean SSH known_hosts
        logger.log("Cleaning SSH known_hosts")
        subprocess.run(["ssh-keygen", "-R", orchestrator_ip], capture_output=True)
        logger.log("SSH known_hosts cleaned")
    
    else:
        logger.step("Skipping Terraform (--skip-terraform)")
        orchestrator_ip = orch_config.get_ip()
        if not orchestrator_ip:
            logger.log_error("Orchestrator IP not found. Deploy with Terraform first.")
            raise SystemExit(1)
        logger.log(f"Using existing orchestrator IP: {orchestrator_ip}")
    
    # Ansible
    logger.step("Configuring services with Ansible")
    
    from cli.ansible_utils import build_ansible_command
    
    ansible_dir = project_root / "shared" / "ansible"
    
    # Prepare ansible vars
    ansible_vars = orch_config.to_ansible_vars()
    
    # Add orchestrator IP
    ansible_env_vars = {
        "superdeploy_root": str(project_root),
        "orchestrator_ip": orchestrator_ip,
    }
    
    # Build ansible command
    ansible_tags = tags if tags else "foundation,addons"
    
    logger.log(f"Running ansible with tags: {ansible_tags}")
    if start_at_task:
        logger.log(f"Resuming from task: {start_at_task}")
    
    ansible_cmd = build_ansible_command(
        ansible_dir=ansible_dir,
        project_root=project_root,
        project_config=ansible_vars,
        env_vars=ansible_env_vars,
        tags=ansible_tags,
        project_name="orchestrator",
        ask_become_pass=False,
        start_at_task=start_at_task,
    )
    
    logger.log_command(ansible_cmd)
    
    # Run ansible with real-time output streaming and task tracking
    import re
    import time
    from rich.tree import Tree
    from rich.live import Live
    from rich.text import Text
    
    # Create progress tree
    progress_tree = Tree("🔧 [cyan]Configuring Orchestrator[/cyan]")
    current_role = None
    current_role_node = None
    current_task_node = None
    role_start_time = None
    task_start_time = None
    
    def format_duration(seconds):
        """Format duration as 1m 23s or 45s"""
        if seconds < 60:
            return f"{int(seconds)}s"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs:02d}s"
    
    with Live(progress_tree, console=console, refresh_per_second=4) as live:
        process = subprocess.Popen(
            ansible_cmd,
            shell=True,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Parse ansible output for task names and timing
        task_pattern = re.compile(r'^\s*TASK \[(.*?)\]')
        play_pattern = re.compile(r'^\s*PLAY \[(.*?)\]')
        timing_pattern = re.compile(r'^\w+\s+\d+\s+\w+\s+\d+\s+[\d:]+\s+[+-]\d+\s+\(([\d:\.]+)\)')
        
        for line in process.stdout:
            line = line.rstrip()
            if line:
                # Write everything to log
                logger.log_output(line, "stdout")
                
                # Parse for display
                play_match = play_pattern.match(line)
                task_match = task_pattern.match(line)
                timing_match = timing_pattern.search(line)
                
                if play_match:
                    play_name = play_match.group(1)
                    if play_name != "Gathering Facts":
                        current_role = play_name
                        role_start_time = time.time()
                        current_role_node = progress_tree.add(f"[yellow]▶[/yellow] {play_name}")
                        live.refresh()
                
                elif task_match:
                    task_name = task_match.group(1)
                    # Skip common noise tasks
                    if not any(skip in task_name.lower() for skip in ['gathering facts', 'setup']):
                        task_start_time = time.time()
                        # Extract role and task name
                        if ' : ' in task_name:
                            role_part, task_part = task_name.split(' : ', 1)
                            # Check if we need a new role node
                            if current_role != role_part:
                                current_role = role_part
                                role_start_time = time.time()
                                clean_role = role_part.split('/')[-1].replace('-', ' ').title()
                                current_role_node = progress_tree.add(f"[yellow]▶[/yellow] {clean_role}")
                            if current_role_node:
                                current_task_node = current_role_node.add(f"[dim]→ {task_part}[/dim]")
                        else:
                            if not current_role_node:
                                current_role_node = progress_tree.add(f"[yellow]▶[/yellow] Tasks")
                            current_task_node = current_role_node.add(f"[dim]→ {task_name}[/dim]")
                        live.refresh()
                
                elif timing_match and current_task_node:
                    # Update task with timing
                    duration_str = timing_match.group(1)
                    # Parse duration like "0:00:05.123"
                    parts = duration_str.split(':')
                    if len(parts) == 3:
                        hours, mins, secs = parts
                        total_secs = int(hours) * 3600 + int(mins) * 60 + float(secs)
                        if total_secs >= 1:  # Only show if >= 1 second
                            task_text = current_task_node.label
                            # Remove old timing if exists
                            if '[' in str(task_text):
                                task_text = str(task_text).split('[')[0].strip()
                            current_task_node.label = f"{task_text} [dim cyan]{format_duration(total_secs)}[/dim cyan]"
                            
                            # Update role total time
                            if role_start_time and current_role_node:
                                role_duration = time.time() - role_start_time
                                role_text = str(current_role_node.label).split('[dim')[0].strip()
                                current_role_node.label = f"{role_text} [dim cyan]({format_duration(role_duration)})[/dim cyan]"
                            
                            live.refresh()
        
        process.wait()
        result_returncode = process.returncode
    
    if result_returncode != 0:
        logger.log_error("Ansible configuration failed", context="Check logs for details")
        raise SystemExit(1)
    
    console.print("[green]✓ Orchestrator configured[/green]")
    
    logger.success("Services configured successfully")
    
    # Display info
    if not verbose:
        console.print(f"\n[cyan]📍 Orchestrator IP:[/cyan] {orchestrator_ip}")
        console.print(f"[cyan]🌐 Forgejo:[/cyan] http://{orchestrator_ip}:3001")
        console.print(f"[cyan]📊 Grafana:[/cyan] http://{orchestrator_ip}:3000")
        console.print(f"[cyan]📈 Prometheus:[/cyan] http://{orchestrator_ip}:9090")
