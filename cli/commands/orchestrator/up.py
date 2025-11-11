"""Orchestrator deployment command."""

import click
import subprocess
import time
import json
from pathlib import Path

from cli.base import BaseCommand
from cli.ui_components import show_header
from cli.logger import DeployLogger, run_with_progress
from cli.core.orchestrator_loader import OrchestratorLoader
from cli.terraform_utils import select_workspace
from cli.ansible_utils import build_ansible_command
from cli.ansible_runner import AnsibleRunner


class OrchestratorUpCommand(BaseCommand):
    """Deploy orchestrator VM with monitoring."""

    def __init__(
        self,
        skip_terraform: bool = False,
        preserve_ip: bool = False,
        addon: str = None,
        tags: str = None,
        verbose: bool = False,
        force: bool = False,
    ):
        super().__init__(verbose=verbose)
        self.skip_terraform = skip_terraform
        self.preserve_ip = preserve_ip
        self.addon = addon
        self.tags = tags
        self.force = force

    def execute(self) -> None:
        """Execute up command."""
        if not self.verbose:
            show_header(
                title="Orchestrator Deployment",
                subtitle="Deploying monitoring infrastructure (Prometheus + Grafana)",
                show_logo=True,
                console=self.console,
            )

        project_root = Path.cwd()
        shared_dir = project_root / "shared"

        # Initialize logger
        with DeployLogger("orchestrator", "up", verbose=self.verbose) as logger:
            try:
                _deploy_orchestrator(
                    logger,
                    self.console,
                    project_root,
                    shared_dir,
                    self.skip_terraform,
                    self.preserve_ip,
                    self.addon,
                    self.tags,
                    self.verbose,
                    self.force,
                )

                if not self.verbose:
                    self.console.print(
                        "\n[color(248)]Orchestrator deployed.[/color(248)]"
                    )

            except Exception as e:
                logger.log_error(str(e), context="Orchestrator deployment failed")
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
                raise SystemExit(1)


@click.command(name="orchestrator:up")
@click.option(
    "--skip-terraform", is_flag=True, help="Skip Terraform (VM already exists)"
)
@click.option(
    "--preserve-ip",
    is_flag=True,
    help="Preserve static IP on destroy (for production)",
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
@click.option(
    "--force",
    is_flag=True,
    help="Force deployment (ignore state, re-run everything)",
)
def orchestrator_up(skip_terraform, preserve_ip, addon, tags, verbose, force):
    """Deploy orchestrator VM with monitoring (runs Terraform + Ansible by default)"""
    cmd = OrchestratorUpCommand(
        skip_terraform=skip_terraform,
        preserve_ip=preserve_ip,
        addon=addon,
        tags=tags,
        verbose=verbose,
        force=force,
    )
    cmd.run()


def _deploy_orchestrator(
    logger,
    console,
    project_root,
    shared_dir,
    skip_terraform,
    preserve_ip,
    addon,
    tags,
    verbose,
    force,
):
    """Internal function for orchestrator deployment with logging"""

    logger.step("[1/3] Setup & Infrastructure")

    # Load orchestrator config
    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
        console.print("  [dim]✓ Configuration loaded[/dim]")
    except FileNotFoundError as e:
        logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Force mode: Clear state to trigger full re-deployment
    if force:
        state_file = shared_dir / "orchestrator" / "state.yml"
        if state_file.exists():
            state_file.unlink()
            logger.log("🗑️  State cleared (force mode)")
            logger.log("")

    # Check state and detect changes (unless forced or specific addon)
    if not force and not addon:
        logger.log("Detecting changes...")

        # Simple state check for orchestrator (different from project state management)
        state = orch_config.state_manager.load_state()
        is_deployed = state.get("deployed", False)
        vm_status = state.get("vm", {}).get("status", "")

        # If VM is only provisioned (not fully configured), continue with Ansible
        if vm_status == "provisioned":
            logger.log("")
            logger.log("VM is provisioned but not fully configured.")
            logger.log("Continuing with Ansible configuration...")
            logger.log("")
            # Don't skip, continue to Ansible
        elif is_deployed:
            # Compare config hash (same as project state manager)
            last_applied = state.get("last_applied", {})
            last_hash = last_applied.get("config_hash", "")
            current_hash = orch_config.state_manager._calculate_config_hash()

            if current_hash == last_hash:
                logger.success("✓ No changes detected. Infrastructure is up to date.")
                logger.log("")
                logger.log("Current state:")
                logger.log(f"  • VM deployed: {is_deployed}")
                logger.log(f"  • IP: {state.get('orchestrator_ip', 'N/A')}")
                logger.log("")
                logger.log("To force re-deployment, use: --force")
                logger.log("To deploy specific addon, use: --addon <name>")
                return
            else:
                logger.log("")
                logger.log("Detected changes in configuration")

                # Try to determine what changed
                last_config = state.get("config", {})

                # Check VM config changes
                if orch_config.config.get("vm") != last_config.get("vm"):
                    logger.log("  • VM configuration changed")
                    skip_terraform = False  # Need terraform
                else:
                    logger.log("  • VM configuration unchanged")
                    skip_terraform = True  # Skip terraform

                # Check addon configs
                if orch_config.config.get("grafana") != last_config.get("grafana"):
                    logger.log("  • Grafana configuration changed")
                if orch_config.config.get("prometheus") != last_config.get(
                    "prometheus"
                ):
                    logger.log("  • Prometheus configuration changed")

                logger.log("")
        else:
            logger.log("First deployment detected")
    elif force:
        logger.log("Force mode enabled, running full deployment")
    elif addon:
        logger.log(f"Deploying specific addon: {addon}")

    # Generate and save secrets
    logger.log("Checking secrets...")

    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    # Initialize secrets using secret manager
    secrets = orch_config.initialize_secrets()

    if secrets:
        logger.log("✓ Secrets verified")
    else:
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
        # First ensure we're on default workspace, then init
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

        # Init
        try:
            returncode, stdout, stderr = run_with_progress(
                logger,
                "cd shared/terraform && terraform init -upgrade -migrate-state -input=false -no-color",
                "Initializing Terraform",
                cwd=project_root,
            )

            if returncode != 0:
                logger.log_error("Terraform init failed", context=stderr)
                raise SystemExit(1)

            console.print("  [dim]✓ Terraform initialized[/dim]")
        except Exception as e:
            logger.log_error("Terraform init failed", context=str(e))
            raise SystemExit(1)

        # Select or create orchestrator workspace (silently)
        try:
            select_workspace("orchestrator", create=True)
        except Exception as e:
            logger.log_error("Workspace setup failed", context=str(e))
            raise SystemExit(1)

        # Generate tfvars
        logger.log("Generating terraform variables")
        tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)

        # Preserve IP logic: If preserve_ip is enabled, get current IP from state
        if preserve_ip:
            logger.log("Preserve IP mode enabled - keeping static IP")
            current_ip = orch_config.get_ip()
            if current_ip:
                logger.log(f"Current IP to preserve: {current_ip}")
                # Terraform will use existing IP address by name convention
            else:
                logger.log("No existing IP found, will create new one")

        tfvars_file = (
            project_root / "shared" / "terraform" / "orchestrator.auto.tfvars.json"
        )

        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        logger.log("Terraform vars written to: orchestrator.auto.tfvars.json")

        # Apply
        logger.log("Running terraform apply")
        apply_cmd = "cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings"

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

        outputs = json.loads(result.stdout)

        orchestrator_ip = (
            outputs.get("vm_public_ips", {}).get("value", {}).get("main-0")
        )

        if not orchestrator_ip:
            logger.log_error("Could not find orchestrator IP in terraform outputs")
            logger.log(f"Available outputs: {outputs}")
            raise SystemExit(1)

        # Save only IP to state (VM provisioned, but not yet configured)
        # Full deployment will be marked after Ansible completes successfully
        state = orch_config.state_manager.load_state()
        state["orchestrator_ip"] = orchestrator_ip
        vm_config_data = orch_config.get_vm_config()
        state["vm"] = {
            "name": vm_config_data.get("name", "orchestrator-main-0"),
            "external_ip": orchestrator_ip,
            "deployed_at": vm_config_data.get("deployed_at"),
            "status": "provisioned",  # Not 'running' yet - Ansible pending
            "machine_type": vm_config_data.get("machine_type"),
            "disk_size": vm_config_data.get("disk_size"),
            "services": vm_config_data.get("services", []),
        }
        state["deployed"] = False  # Not fully deployed yet
        orch_config.state_manager.save_state(state)

        # Wait for SSH
        ssh_key = ssh_config.get("key_path", "~/.ssh/superdeploy_deploy")
        ssh_user = ssh_config.get("user", "superdeploy")

        max_attempts = 18
        for attempt in range(1, max_attempts + 1):
            check_cmd = f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{orchestrator_ip} 'sudo -n whoami' 2>&1"
            result = subprocess.run(
                check_cmd, shell=True, capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0 and "root" in result.stdout:
                console.print("  [dim]✓ VM ready[/dim]")
                break

            if attempt < max_attempts:
                time.sleep(10)
        else:
            logger.warning("VM may not be fully ready, continuing anyway...")
            console.print("  [yellow]⚠[/yellow] [dim]VM partially ready[/dim]")

        # Show configuration summary with IP
        console.print(
            f"  [dim]✓ Configuration • Environment • Orchestrator (main-0: {orchestrator_ip})[/dim]"
        )

        # Clean SSH known_hosts
        subprocess.run(["ssh-keygen", "-R", orchestrator_ip], capture_output=True)

    else:
        orchestrator_ip = orch_config.get_ip()
        if not orchestrator_ip:
            logger.log_error("Orchestrator IP not found. Deploy with Terraform first.")
            raise SystemExit(1)

        # Show configuration summary with IP (skip-terraform mode)
        console.print(
            f"  [dim]✓ Configuration • Environment • Orchestrator (main-0: {orchestrator_ip})[/dim]"
        )

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

    ansible_dir = project_root / "shared" / "ansible"

    # Prepare ansible vars
    ansible_vars = orch_config.to_ansible_vars()

    # Load orchestrator secrets from secrets.yml (complete structure including addons)
    orchestrator_secrets_full = orch_config.secret_manager.load_secrets()

    # Add secrets to ansible vars (keep full structure for addon credentials)
    ansible_vars["project_secrets"] = orchestrator_secrets_full

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
        # For orchestrator, deploy monitoring addon
        enabled_addons_list = ["monitoring"]
    else:
        ansible_tags = "foundation,addons"
        # Deploy monitoring addon by default
        enabled_addons_list = ["monitoring"]

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
        force=force,
    )

    # Run ansible with clean tree view (no messy logs)
    runner = AnsibleRunner(logger, title="Configuring Orchestrator", verbose=verbose)
    result_returncode = runner.run(ansible_cmd, cwd=project_root)

    if result_returncode != 0:
        logger.log_error(
            "Ansible configuration failed", context="Check logs for details"
        )
        console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}")
        console.print(
            f"[dim]Ansible detailed log:[/dim] {logger.log_path.parent / f'{logger.log_path.stem}_ansible.log'}\n"
        )
        raise SystemExit(1)

    # Add summary to tree
    if runner.tree_renderer:
        runner.tree_renderer.add_summary_task(
            "Orchestrator configured", "Services configured successfully"
        )

    # Mark deployment as complete (Ansible succeeded)
    orch_config.mark_deployed(
        orchestrator_ip,
        vm_config=orch_config.get_vm_config(),
        config=orch_config.config,
    )

    # Display info and credentials (always show, regardless of verbose mode)
    secrets = orch_config.get_secrets()

    grafana_pass = secrets.get("GRAFANA_ADMIN_PASSWORD", "")

    console.print(f"\n[cyan]📍 Orchestrator IP:[/cyan] {orchestrator_ip}")
    console.print("\n[bold cyan]🔐 Access Credentials:[/bold cyan]")
    console.print("\n[cyan]📊 Grafana (Monitoring):[/cyan]")
    console.print(f"   URL: http://{orchestrator_ip}:3000")
    console.print("   Username: [bold]admin[/bold]")
    console.print(f"   Password: [bold]{grafana_pass}[/bold]")
    console.print("\n[cyan]📈 Prometheus (Metrics):[/cyan]")
    console.print(f"   URL: http://{orchestrator_ip}:9090")
    console.print("   [dim](No authentication required)[/dim]")

    console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}")
    console.print(
        f"[dim]Ansible detailed log:[/dim] {logger.log_path.parent / f'{logger.log_path.stem}_ansible.log'}\n"
    )
