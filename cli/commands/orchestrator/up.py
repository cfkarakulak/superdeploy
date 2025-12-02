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
        addon: str = None,
        tags: str = None,
        verbose: bool = False,
        force: bool = False,
        json_output: bool = False,
    ):
        super().__init__(verbose=verbose, json_output=json_output)
        self.skip_terraform = skip_terraform
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
                if logger:
                    logger.log_error(str(e), context="Orchestrator deployment failed")
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
                raise SystemExit(1)


@click.command(name="orchestrator:up")
@click.option(
    "--skip-terraform", is_flag=True, help="Skip Terraform (VM already exists)"
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
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def orchestrator_up(skip_terraform, addon, tags, verbose, force, json_output):
    """Deploy orchestrator VM with monitoring (runs Terraform + Ansible by default)"""
    cmd = OrchestratorUpCommand(
        skip_terraform=skip_terraform,
        addon=addon,
        tags=tags,
        verbose=verbose,
        force=force,
        json_output=json_output,
    )
    cmd.run()


def _deploy_orchestrator(
    logger,
    console,
    project_root,
    shared_dir,
    skip_terraform,
    addon,
    tags,
    verbose,
    force,
):
    """Internal function for orchestrator deployment with logging"""

    if logger:
        logger.step("[1/3] Setup & Infrastructure")

    # Load orchestrator config
    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        orch_config = orchestrator_loader.load()
        console.print("  [dim]✓ Configuration loaded[/dim]")
    except FileNotFoundError as e:
        if logger:
            logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Force mode: Clear state to trigger full re-deployment
    if force:
        state_file = shared_dir / "orchestrator" / "state.yml"
        if state_file.exists():
            state_file.unlink()
            if logger:
                logger.log("🗑️  State cleared (force mode)")
            if logger:
                logger.log("")

    # Check state and detect changes (unless forced or specific addon)
    if not force and not addon:
        if logger:
            logger.log("Detecting changes...")

        # Load state from database
        from cli.database import get_db_session, Project
        import hashlib

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )

            if not db_project:
                if logger:
                    logger.log("First deployment detected (no database record)")
            else:
                # Check if we have orchestrator IP (means fully deployed)
                from cli.database import Secret, VM

                secret = (
                    db.query(Secret)
                    .filter(
                        Secret.project_id == db_project.id,
                        Secret.key == "ORCHESTRATOR_IP",
                    )
                    .first()
                )
                is_deployed = secret is not None and secret.value is not None
                orchestrator_ip = secret.value if secret else None

                # Check VM status
                vm = db.query(VM).filter(VM.project_id == db_project.id).first()
                vm_status = vm.status if vm else ""

                # Load config hash from project metadata (stored as JSON in extra field if exists)
                stored_config_hash = getattr(db_project, "config_hash", None) or ""

                # If VM is only provisioned (not fully configured), continue with Ansible
                if vm_status == "provisioned":
                    if logger:
                        logger.log("")
                    if logger:
                        logger.log("VM is provisioned but not fully configured.")
                    if logger:
                        logger.log("Continuing with Ansible configuration...")
                    if logger:
                        logger.log("")
                    # Don't skip, continue to Ansible
                elif is_deployed:
                    # Compare config hash
                    current_config_str = str(orch_config.config)
                    current_hash = hashlib.sha256(
                        current_config_str.encode()
                    ).hexdigest()

                    if current_hash == stored_config_hash:
                        if logger:
                            logger.success(
                                "No changes detected. Infrastructure is up to date."
                            )
                        if logger:
                            logger.log("")
                        if logger:
                            logger.log("Current state:")
                        if logger:
                            logger.log(f"  • VM deployed: {is_deployed}")
                        if logger:
                            logger.log(f"  • IP: {orchestrator_ip or 'N/A'}")
                        if logger:
                            logger.log("")
                        if logger:
                            logger.log("To force re-deployment, use: --force")
                        if logger:
                            logger.log("To deploy specific addon, use: --addon <name>")
                        return
                    else:
                        if logger:
                            logger.log("")
                        if logger:
                            logger.log("Detected changes in configuration")

                        # Config comparison (no stored config after migration, assume changes)
                        last_config = {}

                        # Check VM config changes
                        if orch_config.config.get("vm") != last_config.get("vm"):
                            if logger:
                                logger.log("  • VM configuration changed")
                            skip_terraform = False  # Need terraform
                        else:
                            if logger:
                                logger.log("  • VM configuration unchanged")
                            skip_terraform = True  # Skip terraform

                        # Check addon configs
                        if orch_config.config.get("grafana") != last_config.get(
                            "grafana"
                        ):
                            if logger:
                                logger.log("  • Grafana configuration changed")
                        if orch_config.config.get("prometheus") != last_config.get(
                            "prometheus"
                        ):
                            if logger:
                                logger.log("  • Prometheus configuration changed")

                        if logger:
                            logger.log("")
        finally:
            db.close()
    elif force:
        if logger:
            logger.log("Force mode enabled, running full deployment")
    elif addon:
        if logger:
            logger.log(f"Deploying specific addon: {addon}")

    # Generate and save secrets
    if logger:
        logger.log("Checking secrets...")

    orchestrator_dir = shared_dir / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    # Initialize secrets using secret manager
    secrets = orch_config.initialize_secrets()

    if secrets:
        if logger:
            logger.log("✓ Secrets verified")
    else:
        if logger:
            logger.log("✓ Secrets generated")

    # Get GCP config
    gcp_config = orch_config.config.get("gcp", {})
    ssh_config = orch_config.config.get("ssh", {})

    gcp_project_id = gcp_config.get("project_id")
    if not gcp_project_id:
        if logger:
            logger.log_error("gcp.project_id not set in database")
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
                if logger:
                    logger.log_error("Terraform init failed", context=stderr)
                raise SystemExit(1)

            console.print("  [dim]✓ Terraform initialized[/dim]")
        except Exception as e:
            if logger:
                logger.log_error("Terraform init failed", context=str(e))
            raise SystemExit(1)

        # Select or create orchestrator workspace (silently)
        try:
            select_workspace("orchestrator", create=True)
        except Exception as e:
            if logger:
                logger.log_error("Workspace setup failed", context=str(e))
            raise SystemExit(1)

        # Generate tfvars
        if logger:
            logger.log("Generating terraform variables")
        tfvars = orch_config.to_terraform_vars(gcp_project_id, ssh_key_path)

        tfvars_file = (
            project_root / "shared" / "terraform" / "orchestrator.auto.tfvars.json"
        )

        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        if logger:
            logger.log("Terraform vars written to: orchestrator.auto.tfvars.json")

        # Apply
        if logger:
            logger.log("Running terraform apply")
        apply_cmd = "cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings"

        returncode, stdout, stderr = run_with_progress(
            logger,
            apply_cmd,
            "Provisioning infrastructure (this may take 2-3 minutes)",
            cwd=project_root,
        )

        if returncode != 0:
            if logger:
                logger.log_error("Terraform apply failed", context=stderr)
            raise SystemExit(1)

        console.print("  [dim]✓ VM provisioned[/dim]")

        # Get outputs
        # Ensure we're in orchestrator workspace
        try:
            select_workspace("orchestrator", create=False)
        except Exception as e:
            if logger:
                logger.log_error(
                    "Failed to select orchestrator workspace", context=str(e)
                )
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
            if logger:
                logger.log_error(
                    "Failed to get terraform outputs", context=result.stderr
                )
            raise SystemExit(1)

        outputs = json.loads(result.stdout)

        orchestrator_ip = (
            outputs.get("vm_public_ips", {}).get("value", {}).get("main-0")
        )

        if not orchestrator_ip:
            if logger:
                logger.log_error("Could not find orchestrator IP in terraform outputs")
            if logger:
                logger.log(f"Available outputs: {outputs}")
            raise SystemExit(1)

        # Get internal IP from Terraform outputs (for VPC peering, Loki, Prometheus)
        orchestrator_internal_ip = (
            outputs.get("vm_internal_ips", {}).get("value", {}).get("main-0")
        )

        # Fallback: try vms_by_role output
        if not orchestrator_internal_ip:
            vms_by_role = outputs.get("vms_by_role", {}).get("value", {})
            main_vms = vms_by_role.get("main", []) or vms_by_role.get(
                "orchestrator", []
            )
            if main_vms and len(main_vms) > 0:
                orchestrator_internal_ip = main_vms[0].get("internal_ip")

        # Final fallback: use reserved orchestrator subnet IP (10.0.0.2)
        if not orchestrator_internal_ip:
            orchestrator_internal_ip = "10.0.0.2"

        # Save only IP to database state (VM provisioned, but not yet configured)
        # Full deployment will be marked after Ansible completes successfully
        from cli.database import get_db_session, Project
        from datetime import datetime

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )

            if not db_project:
                if logger:
                    logger.log_error(
                        "Orchestrator not found in database. Run 'orchestrator:init' first."
                    )
                raise SystemExit(1)

            from cli.database import VM, Secret

            vm_config_data = orch_config.get_vm_config()

            # Save VM to vms table
            vm_name = vm_config_data.get("name", "orchestrator-main-0")
            vm = (
                db.query(VM)
                .filter(VM.project_id == db_project.id, VM.role == "orchestrator")
                .first()
            )
            if not vm:
                vm = VM(
                    project_id=db_project.id,
                    name=vm_name,
                    role="orchestrator",
                    machine_type=vm_config_data.get("machine_type", "e2-medium"),
                    disk_size=vm_config_data.get("disk_size", 50),
                )
                db.add(vm)
            vm.external_ip = orchestrator_ip
            vm.internal_ip = (
                orchestrator_internal_ip  # Save internal IP for VPC peering
            )
            vm.status = "provisioned"

            # Save orchestrator IP to secrets
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == db_project.id, Secret.key == "ORCHESTRATOR_IP"
                )
                .first()
            )
            if not secret:
                secret = Secret(
                    project_id=db_project.id,
                    key="ORCHESTRATOR_IP",
                    value=orchestrator_ip,
                    source="shared",
                    editable=False,
                )
                db.add(secret)
            else:
                secret.value = orchestrator_ip

            db_project.updated_at = datetime.utcnow()
            db.commit()

            if logger:
                logger.log(f"✓ State saved to database (IP: {orchestrator_ip})")
        finally:
            db.close()

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
            if logger:
                logger.warning("VM may not be fully ready, continuing anyway...")
            console.print("  [yellow]⚠[/yellow] [dim]VM partially ready[/dim]")

        # Show configuration summary with IP
        console.print(
            f"  [dim]✓ Configuration • Environment • Orchestrator (main-0: {orchestrator_ip})[/dim]"
        )

        # Clean SSH known_hosts
        subprocess.run(["ssh-keygen", "-R", orchestrator_ip], capture_output=True)

    else:
        # Skip terraform mode - get IP from database
        from cli.database import get_db_session, Project, Secret, VM

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            orchestrator_ip = None
            if db_project:
                # Try secrets first
                secret = (
                    db.query(Secret)
                    .filter(
                        Secret.project_id == db_project.id,
                        Secret.key == "ORCHESTRATOR_IP",
                    )
                    .first()
                )
                if secret:
                    orchestrator_ip = secret.value
                else:
                    # Fallback to VMs table
                    vm = (
                        db.query(VM)
                        .filter(
                            VM.project_id == db_project.id, VM.external_ip.isnot(None)
                        )
                        .first()
                    )
                    if vm:
                        orchestrator_ip = vm.external_ip

            if not orchestrator_ip:
                if logger:
                    logger.log_error(
                        "Orchestrator IP not found in database. Deploy with Terraform first."
                    )
                raise SystemExit(1)
        finally:
            db.close()

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
orchestrator-main-0 ansible_host={orchestrator_ip} internal_ip={orchestrator_internal_ip or "10.0.0.2"} ansible_user={ssh_user} ansible_ssh_private_key_file={ssh_key} ansible_become=yes ansible_become_method=sudo

[all:vars]
ansible_python_interpreter=/usr/bin/python3
orchestrator_internal_ip={orchestrator_internal_ip or "10.0.0.2"}
"""

    with open(inventory_file, "w") as f:
        f.write(inventory_content)

    # Phase 1 complete - show summary
    if logger:
        logger.success(f"Configuration • Secrets • VM @ {orchestrator_ip}")

    # Ansible - Phase 2 & 3
    if logger:
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
        if logger:
            logger.log(f"Deploying only addon(s): {', '.join(enabled_addons_list)}")
    elif tags:
        ansible_tags = tags
        # For orchestrator, deploy monitoring addon
        enabled_addons_list = ["monitoring"]
    else:
        ansible_tags = "foundation,addons"
        # Deploy monitoring addon by default
        enabled_addons_list = ["monitoring"]

    if logger:
        logger.log(f"Running ansible with tags: {ansible_tags}")

    # Get addon metadata from database for proper display
    from cli.database import get_db_session, Project as DBProject
    from sqlalchemy import text

    addon_instances = []
    db = get_db_session()
    try:
        # Get orchestrator project ID
        orch_project = (
            db.query(DBProject).filter(DBProject.name == "orchestrator").first()
        )
        if orch_project:
            # Get addon details from DB
            for addon_name in enabled_addons_list:
                result = db.execute(
                    text("""
                        SELECT type, instance_name, version, plan
                        FROM addons
                        WHERE project_id = :project_id AND type = :addon_name
                        LIMIT 1
                    """),
                    {"project_id": orch_project.id, "addon_name": addon_name},
                )
                addon_row = result.fetchone()

                if addon_row:
                    addon_instances.append(
                        {
                            "full_name": f"{addon_name}.{addon_row[1]}",
                            "type": addon_row[0],
                            "version": addon_row[2] or "latest",
                            "plan": addon_row[3] or "standard",
                            "category": "monitoring",
                            "name": addon_row[1],
                            "options": {},
                        }
                    )
                else:
                    # Fallback for addons not in DB yet
                    addon_instances.append(
                        {
                            "full_name": f"{addon_name}.primary",
                            "type": addon_name,
                            "version": "latest",
                            "plan": "standard",
                            "category": "monitoring",
                            "name": "primary",
                            "options": {},
                        }
                    )
    finally:
        db.close()

    # Add addon instances to ansible vars if we have them
    if addon_instances:
        ansible_vars["addon_instances"] = addon_instances

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
        if logger:
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
    from cli.database import get_db_session, Project
    import hashlib
    from datetime import datetime

    db = get_db_session()
    try:
        db_project = db.query(Project).filter(Project.name == "orchestrator").first()

        if db_project:
            from cli.database import VM, Secret

            vm_config_data = orch_config.get_vm_config()

            # Update VM status to running
            vm = (
                db.query(VM)
                .filter(VM.project_id == db_project.id, VM.role == "orchestrator")
                .first()
            )
            if vm:
                vm.status = "running"
                vm.external_ip = orchestrator_ip
            else:
                vm = VM(
                    project_id=db_project.id,
                    name=vm_config_data.get("name", "orchestrator-main-0"),
                    role="orchestrator",
                    external_ip=orchestrator_ip,
                    status="running",
                    machine_type=vm_config_data.get("machine_type", "e2-medium"),
                    disk_size=vm_config_data.get("disk_size", 50),
                )
                db.add(vm)

            # Update orchestrator IP in secrets
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == db_project.id, Secret.key == "ORCHESTRATOR_IP"
                )
                .first()
            )
            if not secret:
                secret = Secret(
                    project_id=db_project.id,
                    key="ORCHESTRATOR_IP",
                    value=orchestrator_ip,
                    source="shared",
                    editable=False,
                )
                db.add(secret)
            else:
                secret.value = orchestrator_ip

            db_project.updated_at = datetime.utcnow()
            db.commit()

            # Log deployment activity
            from cli.database import ActivityLog

            activity = ActivityLog(
                project_name="orchestrator",
                action="orchestrator:up",
                actor="cli",
                details={
                    "orchestrator_ip": orchestrator_ip,
                    "vm_status": "running",
                    "services": ["prometheus", "grafana"],
                },
                created_at=datetime.utcnow(),
            )
            db.add(activity)
            db.commit()

            if logger:
                logger.log("✓ Deployment marked as complete in database")
    finally:
        db.close()

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
