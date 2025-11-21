"""SuperDeploy CLI - Up command (with smart deployment and change detection)"""

import click
import subprocess
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple

from cli.base import ProjectCommand
from cli.logger import DeployLogger, run_with_progress
from cli.services.deployment_validator import DeploymentValidator
from cli.services.secret_ip_updater import SecretIPUpdater
from cli.services.ansible_inventory_generator import AnsibleInventoryGenerator


@dataclass
class DeploymentOptions:
    """Options for deployment execution."""

    skip_terraform: bool = False
    skip_ansible: bool = False
    skip: Tuple[str, ...] = ()
    addon: Optional[str] = None
    tags: Optional[str] = None
    preserve_ip: bool = False
    force: bool = False
    dry_run: bool = False


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI color codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class UpCommand(ProjectCommand):
    """Deploy project infrastructure."""

    def __init__(
        self,
        project_name: str,
        skip_terraform: bool = False,
        skip_ansible: bool = False,
        skip: tuple = (),
        addon: str = None,
        tags: str = None,
        preserve_ip: bool = False,
        verbose: bool = False,
        force: bool = False,
        dry_run: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.skip_terraform = skip_terraform
        self.skip_ansible = skip_ansible
        self.skip = skip
        self.addon = addon
        self.tags = tags
        self.preserve_ip = preserve_ip
        self.force = force
        self.dry_run = dry_run

    def execute(self) -> None:
        """Execute up command."""
        self._execute_deployment()

    def _ensure_addon_secrets(self, logger) -> None:
        """
        Auto-generate missing addon secrets before deployment.

        This is idempotent - only creates secrets that don't exist.
        Follows "lazy generation" principle - secrets created when needed.
        """
        from cli.database import get_db_session, Secret, Project
        import secrets as python_secrets
        import string

        def generate_password(length=32):
            """Generate a secure random password."""
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            return "".join(python_secrets.choice(alphabet) for _ in range(length))

        # Load project config from database to see which addons are configured
        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                logger.warning(f"Project '{self.project_name}' not found in database")
                return

            addons = project.addons_config or {}
        finally:
            db.close()

        if not addons:
            return  # No addons configured

        # Re-open DB connection for secret operations
        db = get_db_session()
        try:
            # Check which addon secrets already exist
            existing_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.source == "addon",
                )
                .all()
            )
            existing_keys = {s.key for s in existing_secrets}

            secrets_to_create = []

            # Generate missing addon secrets based on configuration
            if "databases" in addons:
                for instance_name, config_data in addons["databases"].items():
                    addon_type = config_data.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "postgres":
                        addon_secrets = {
                            f"{addon_key}.PORT": "5432",
                            f"{addon_key}.USER": f"{self.project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{self.project_name}_db",
                        }
                    elif addon_type == "mysql":
                        addon_secrets = {
                            f"{addon_key}.PORT": "3306",
                            f"{addon_key}.USER": f"{self.project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{self.project_name}_db",
                        }
                    elif addon_type == "mongodb":
                        addon_secrets = {
                            f"{addon_key}.PORT": "27017",
                            f"{addon_key}.USER": f"{self.project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{self.project_name}_db",
                        }
                    else:
                        continue

                    for key, value in addon_secrets.items():
                        if key not in existing_keys:
                            secrets_to_create.append(
                                (key, value, addon_type, instance_name)
                            )

            if "queues" in addons:
                for instance_name, config_data in addons["queues"].items():
                    addon_type = config_data.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "rabbitmq":
                        addon_secrets = {
                            f"{addon_key}.PORT": "5672",
                            f"{addon_key}.MANAGEMENT_PORT": "15672",
                            f"{addon_key}.USER": f"{self.project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                        }

                        for key, value in addon_secrets.items():
                            if key not in existing_keys:
                                secrets_to_create.append(
                                    (key, value, addon_type, instance_name)
                                )

            if "caches" in addons:
                for instance_name, config_data in addons["caches"].items():
                    addon_type = config_data.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "redis":
                        addon_secrets = {
                            f"{addon_key}.PORT": "6379",
                            f"{addon_key}.PASSWORD": generate_password(),
                        }
                    elif addon_type == "memcached":
                        addon_secrets = {
                            f"{addon_key}.PORT": "11211",
                        }
                    else:
                        continue

                    for key, value in addon_secrets.items():
                        if key not in existing_keys:
                            secrets_to_create.append(
                                (key, value, addon_type, instance_name)
                            )

            # Create missing secrets in database
            if secrets_to_create:
                logger.log(
                    f"💾 Auto-generating {len(secrets_to_create)} addon credential(s)..."
                )

                for key, value, addon_type, instance_name in secrets_to_create:
                    secret = Secret(
                        project_name=self.project_name,
                        app_name=None,
                        key=key,
                        value=value,
                        environment="production",
                        source="addon",
                        editable=False,
                    )
                    db.add(secret)
                    logger.log(f"  ✓ Generated: {key}")

                db.commit()
                logger.log("✓ Addon credentials saved to database")
            else:
                logger.log("✓ All addon credentials already exist", level="DEBUG")

        except Exception as e:
            db.rollback()
            logger.log_error(f"Failed to generate addon secrets: {e}")
            raise
        finally:
            db.close()

    def _execute_deployment(self) -> None:
        """
        Internal deployment logic.

        This function contains the core deployment workflow:
        - Validate secrets
        - Detect changes automatically
        - Generate workflows if needed
        - Provision VMs with Terraform
        - Configure services with Ansible
        - Sync secrets to GitHub

        Smart & idempotent - runs only what's needed.
        """
        if not self.verbose:
            self.show_header(
                title="Infrastructure Deployment",
                subtitle="Smart deployment with change detection",
            )

        # Initialize logger
        with DeployLogger(self.project_name, "up", verbose=self.verbose) as logger:
            try:
                # Auto-generate missing addon secrets before deployment
                self._ensure_addon_secrets(logger)

                # Validate secrets before deployment
                validator = DeploymentValidator(
                    self.project_root, self.config_service, self.project_name
                )
                validation_errors = validator.validate_secrets(logger)

                if validation_errors:
                    self._display_validation_errors(validation_errors)
                    raise SystemExit(1)

                # Force mode: Clear state to trigger full re-deployment
                if self.force:
                    from cli.state_manager import StateManager

                    state_mgr = StateManager(self.project_root, self.project_name)
                    state_file = (
                        self.project_root / "projects" / self.project_name / "state.yml"
                    )
                    if state_file.exists():
                        state_file.unlink()
                        if logger:
                            logger.log("🗑️  State cleared (force mode)")
                        if logger:
                            logger.log("")

                # Change detection (smart deployment)
                changes = None  # Initialize - will be set if change detection runs

                # Force mode or skip flags - no change detection
                if self.force or self.skip_terraform or self.skip_ansible:
                    # Force mode: Skip change detection, deploy everything
                    if self.force:
                        if logger:
                            logger.log("🔄 Force mode: skipping change detection")
                        if logger:
                            logger.log("")
                    # No change detection needed
                    changes = None
                else:
                    # Normal mode: Detect changes
                    from cli.state_manager import StateManager

                    try:
                        project_config = self.config_service.load_project_config(
                            self.project_name
                        )
                    except FileNotFoundError:
                        if logger:
                            logger.log_error(f"Project not found: {self.project_name}")
                        raise SystemExit(1)
                    except ValueError as e:
                        if logger:
                            logger.log_error(f"Invalid configuration: {e}")
                        raise SystemExit(1)

                    # Detect changes
                    state_mgr = StateManager(self.project_root, self.project_name)
                    changes, state = state_mgr.detect_changes(project_config)

                    # Dry-run mode
                    if self.dry_run:
                        if logger:
                            logger.log("🔍 Dry-run mode: showing what would be done")
                        if logger:
                            logger.log("")

                        if not changes["has_changes"]:
                            if logger:
                                logger.success(
                                    "✅ No changes detected. Infrastructure is up to date."
                                )
                            return

                        # Show changes (mini plan)
                        if changes["vms"]["added"]:
                            if logger:
                                logger.log(
                                    f"VMs to create: {', '.join(changes['vms']['added'])}"
                                )
                        if changes["vms"]["modified"]:
                            modified_vms = [
                                v["name"] for v in changes["vms"]["modified"]
                            ]
                            if logger:
                                logger.log(f"VMs to modify: {', '.join(modified_vms)}")
                        if changes["addons"]["added"]:
                            if logger:
                                logger.log(
                                    f"Addons to install: {', '.join(changes['addons']['added'])}"
                                )
                        if changes["apps"]["added"]:
                            if logger:
                                logger.log(
                                    f"Apps to setup: {', '.join(changes['apps']['added'])}"
                                )

                        if logger:
                            logger.log("")
                        if logger:
                            logger.log("Run without --dry-run to apply changes")
                        return

                    # No changes - skip deployment
                    if not changes["has_changes"]:
                        if logger:
                            logger.log("🔍 Detecting changes...")
                        if logger:
                            logger.log("")
                        if logger:
                            logger.success("✅ No changes detected.")
                        if logger:
                            logger.log("")
                        if logger:
                            logger.log("Infrastructure is up to date with config.yml")
                        if logger:
                            logger.log("")
                        if logger:
                            logger.log(
                                f"To force update: superdeploy {self.project_name}:up --force"
                            )
                        return

                    # Show detected changes
                    if logger:
                        logger.log("🔍 Detecting changes...")
                    if logger:
                        logger.log("")

                    # Check if any VMs need configuration
                    state = state_mgr.load_state()
                    vms_needing_config = []
                    for vm_name, vm_data in state.get("vms", {}).items():
                        if vm_data.get("status") == "provisioned":
                            vms_needing_config.append(vm_name)

                    if vms_needing_config:
                        if logger:
                            logger.log(
                                f"  [yellow]⚙ VMs need configuration:[/yellow] {', '.join(vms_needing_config)}"
                            )

                    if changes["vms"]["added"]:
                        if logger:
                            logger.log(
                                f"  [green]+ VMs to create:[/green] {', '.join(changes['vms']['added'])}"
                            )
                    if changes["vms"]["modified"]:
                        modified_vms = [v["name"] for v in changes["vms"]["modified"]]
                        if logger:
                            logger.log(
                                f"  [yellow]~ VMs to modify:[/yellow] {', '.join(modified_vms)}"
                            )
                    if changes["addons"]["added"]:
                        if logger:
                            logger.log(
                                f"  [green]+ Addons to install:[/green] {', '.join(changes['addons']['added'])}"
                            )
                    if changes["apps"]["added"]:
                        if logger:
                            logger.log(
                                f"  [green]+ Apps to setup:[/green] {', '.join(changes['apps']['added'])}"
                            )

                    if logger:
                        logger.log("")
                    if logger:
                        logger.log("Proceeding with deployment...")
                    if logger:
                        logger.log("")

                    # Override skip flags based on what's needed
                    if not changes["needs_terraform"]:
                        self.skip_terraform = True
                        if logger:
                            logger.log(
                                "  [dim]⏭ Skipping Terraform (no infrastructure changes)[/dim]"
                            )

                    if not changes["needs_ansible"]:
                        self.skip_ansible = True
                        if logger:
                            logger.log(
                                "  [dim]⏭ Skipping Ansible (no service changes)[/dim]"
                            )

                    if not changes["needs_sync"]:
                        if logger:
                            logger.log("  [dim]⏭ No secret changes detected[/dim]")

                    # Auto-generate workflows if needed
                    if changes["needs_generate"]:
                        if logger:
                            logger.log("  [cyan]→ Auto-generating workflows...[/cyan]")

                        # Call generate command directly (uses same environment)
                        from cli.commands.generate import GenerateCommand

                        try:
                            gen_cmd = GenerateCommand(
                                project_name=self.project_name, verbose=self.verbose
                            )
                            gen_cmd.execute()
                            if logger:
                                logger.log("  [dim]✓ Workflows generated[/dim]")
                        except Exception as e:
                            if logger:
                                logger.log_error("Workflow generation failed")
                            if logger:
                                logger.warning(f"  {str(e)}")
                            raise SystemExit(1)

                    if logger:
                        logger.log("")

                self._deploy_project(
                    logger,
                    changes if not self.force else None,  # Pass changes for smart skip
                )

                # Update state after successful deployment (if not skipped)
                if not self.force and not self.dry_run:
                    from cli.state_manager import StateManager

                    project_config = self.config_service.load_project_config(
                        self.project_name
                    )

                    state_mgr = StateManager(self.project_root, self.project_name)
                    state_mgr.update_from_config(project_config)

                    if logger:
                        logger.log("")
                    if logger:
                        logger.log("💾 State saved")

            except Exception as e:
                if logger:
                    logger.log_error(
                        str(e), context=f"Project {self.project_name} deployment failed"
                    )
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
                raise SystemExit(1)

    def _deploy_project(self, logger, changes=None):
        """Deploy project infrastructure and services."""
        _deploy_project_internal(
            logger,
            self.console,
            self.project_root,
            self.config_service,
            self.project_name,
            self.skip_terraform,
            self.skip_ansible,
            self.skip,
            self.addon,
            self.tags,
            self.preserve_ip,
            self.verbose,
            self.force,
            changes,
        )

    def _display_validation_errors(self, errors: List[str]) -> None:
        """Display validation errors in a formatted manner."""
        self.console.print("")
        self.console.print("[red]❌ Validation Failed[/red]")
        self.console.print("")
        self.console.print("Please fix the following issues:")
        self.console.print("")
        for error in errors:
            self.console.print(f"  [red]•[/red] {error}")
        self.console.print("")
        self.console.print(
            f"[dim]Edit secrets:[/dim] Use 'superdeploy {self.project_name}:config:set KEY VALUE' or dashboard"
        )
        self.console.print("")


def _deploy_project_internal(
    logger,
    console,
    project_root,
    config_service,
    project,
    skip_terraform,
    skip_ansible,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
    force,
    changes=None,  # For smart skip logic
):
    """Internal function for project deployment with logging"""

    if logger:
        logger.step("[1/4] Setup & Infrastructure")

    # Load project config
    from cli.core.orchestrator_loader import OrchestratorLoader

    shared_dir = project_root / "shared"

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        project_config_obj = config_service.load_project_config(project)
        console.print("  [dim]✓ Configuration loaded[/dim]")
    except FileNotFoundError as e:
        if logger:
            logger.log_error(str(e), context=f"Project '{project}' not found")
        raise SystemExit(1)
    except ValueError as e:
        if logger:
            logger.log_error(f"Invalid configuration: {e}")
        raise SystemExit(1)

    # Load orchestrator config
    try:
        orchestrator_config = orchestrator_loader.load()

        # Check if orchestrator is deployed
        if not orchestrator_config.is_deployed():
            if logger:
                logger.log_error(
                    "Orchestrator not deployed yet",
                    context="Deploy it first: [red]superdeploy orchestrator up[/red]",
                )
            raise SystemExit(1)

        orchestrator_ip = orchestrator_config.get_ip()
        if not orchestrator_ip:
            if logger:
                logger.log_error("Orchestrator IP not found")
            raise SystemExit(1)

        console.print(f"  [dim]✓ Orchestrator @ {orchestrator_ip}[/dim]")

    except FileNotFoundError as e:
        if logger:
            logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Load project config and environment
    from cli.utils import validate_env_vars
    from cli.secret_manager import SecretManager

    project_dir = project_root / "projects" / project

    # Load project config (using config_service from parameter)
    project_config_obj = config_service.load_project_config(project)

    # Load from database
    secret_mgr = SecretManager(project_root, project, "production")
    secrets_data = secret_mgr.load_secrets()

    # Build env dict from config.yml + database secrets
    env = {
        "GCP_PROJECT_ID": project_config_obj.raw_config["cloud"]["gcp"]["project_id"],
        "GCP_REGION": project_config_obj.raw_config["cloud"]["gcp"]["region"],
        "SSH_KEY_PATH": project_config_obj.raw_config["cloud"]["ssh"]["key_path"],
        "SSH_USER": project_config_obj.raw_config["cloud"]["ssh"]["user"],
    }

    # Add secrets to env
    if secrets_data and secrets_data.get("shared"):
        env.update(secrets_data["shared"])

    # Validate required vars
    required = ["GCP_PROJECT_ID", "GCP_REGION", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        if logger:
            logger.log_error(
                "Missing required environment variables", context=", ".join(required)
            )
        raise SystemExit(1)

    if logger:
        logger.log("✓ Environment validated")

    # Terraform - Smart skip logic
    if not skip_terraform:
        # Smart skip: if no terraform changes, skip it
        if changes and not changes.get("needs_terraform", True):
            if logger:
                logger.log("[dim]✓ Terraform: no VM changes, skipping[/dim]")
            skip_terraform = True
        else:
            if logger:
                logger.log("Provisioning VMs (3-5 min)...")

            from cli.terraform_utils import (
                terraform_refresh,
                generate_tfvars,
            )

            # Ensure we're on default workspace before init (prevents interactive prompt)
            if logger:
                logger.log("Ensuring default workspace")
            terraform_dir = project_root / "shared" / "terraform"
            terraform_state_dir = terraform_dir / ".terraform"

            if terraform_state_dir.exists():
                # Try to switch to default workspace silently
                subprocess.run(
                    "terraform workspace select default 2>/dev/null || true",
                    shell=True,
                    cwd=terraform_dir,
                    capture_output=True,
                )

            # Init with migrate-state to automatically migrate workspaces without prompts
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

            # Generate tfvars
            tfvars_file = generate_tfvars(project_config_obj, preserve_ip=preserve_ip)

            # Select or create workspace using terraform_utils
            from cli.terraform_utils import select_workspace

            try:
                select_workspace(project, create=True)
            except Exception as e:
                if logger:
                    logger.log_error("Workspace setup failed", context=str(e))
                raise SystemExit(1)

            # Refresh state
            try:
                terraform_refresh(project, project_config_obj)
            except Exception:
                pass  # May fail on first run, that's ok

            # Apply
            apply_cmd = f"cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings -var-file={tfvars_file.name}"

            if preserve_ip:
                pass  # Preserve IP mode (implicit in tfvars)

            returncode, stdout, stderr = run_with_progress(
                logger,
                apply_cmd,
                "Provisioning infrastructure (this may take 3-5 minutes)",
                cwd=project_root,
            )

            if returncode != 0:
                if logger:
                    logger.log_error("Terraform apply failed", context=stderr)
                raise SystemExit(1)

            console.print("  [dim]✓ VMs provisioned[/dim]")

            # Get VM IPs from Terraform outputs
            from cli.terraform_utils import get_terraform_outputs

            outputs = get_terraform_outputs(project)
            public_ips = outputs.get("vm_public_ips", {}).get("value", {})
            internal_ips = outputs.get("vm_internal_ips", {}).get("value", {})

            # Update state: VMs provisioned WITH IPs
            from cli.state_manager import StateManager

            state_mgr = StateManager(project_root, project)
            state_mgr.mark_vms_provisioned(
                project_config_obj.raw_config.get("vms", {}),
                vm_ips={"external": public_ips, "internal": internal_ips},
            )

            # Save VMs to database
            vms_by_role = outputs.get("vms_by_role", {}).get("value", {})
            if vms_by_role:
                from cli.database import get_db_session
                from sqlalchemy import text

                db = get_db_session()
                try:
                    # Get project ID
                    project_result = db.execute(
                        text("SELECT id FROM projects WHERE name = :project"),
                        {"project": project},
                    )
                    project_row = project_result.fetchone()
                    if project_row:
                        project_id = project_row[0]

                        # Insert/Update VMs
                        for role, vms in vms_by_role.items():
                            for vm in vms:
                                # Check if VM exists
                                check = db.execute(
                                    text("SELECT id FROM vms WHERE name = :name"),
                                    {"name": vm["name"]},
                                )
                                existing = check.fetchone()

                                if existing:
                                    # Update
                                    db.execute(
                                        text("""
                                            UPDATE vms 
                                            SET external_ip = :external_ip, 
                                                internal_ip = :internal_ip,
                                                role = :role,
                                                status = 'running'
                                            WHERE name = :name
                                        """),
                                        {
                                            "name": vm["name"],
                                            "external_ip": vm["external_ip"],
                                            "internal_ip": vm["internal_ip"],
                                            "role": role,
                                        },
                                    )
                                else:
                                    # Insert
                                    db.execute(
                                        text("""
                                            INSERT INTO vms (project_id, name, role, external_ip, internal_ip, machine_type, status)
                                            VALUES (:project_id, :name, :role, :external_ip, :internal_ip, :machine_type, :status)
                                        """),
                                        {
                                            "project_id": project_id,
                                            "name": vm["name"],
                                            "role": role,
                                            "external_ip": vm["external_ip"],
                                            "internal_ip": vm["internal_ip"],
                                            "machine_type": "e2-medium",  # TODO: Get from config
                                            "status": "running",
                                        },
                                    )

                        db.commit()
                        if logger:
                            logger.log("✓ VMs saved to database")
                finally:
                    db.close()

            # Add IPs to env dict for Ansible
            for vm_key, ip in sorted(public_ips.items()):
                env_key = vm_key.upper().replace("-", "_")
                env[f"{env_key}_EXTERNAL_IP"] = ip

            for vm_key, ip in sorted(internal_ips.items()):
                env_key = vm_key.upper().replace("-", "_")
                env[f"{env_key}_INTERNAL_IP"] = ip

            if logger:
                logger.log("✓ VM IPs loaded to environment")

            # Wait for VMs
            if logger:
                logger.log("Waiting for VMs to be ready...")

            if public_ips:
                import time

                ssh_key = env.get("SSH_KEY_PATH")
                ssh_user = env.get("SSH_USER", "superdeploy")

                # Check each VM
                max_attempts = 18
                all_ready = True

                for vm_name, vm_ip in public_ips.items():
                    if logger:
                        logger.log(f"Checking {vm_name} ({vm_ip})")
                    vm_ready = False

                    for attempt in range(1, max_attempts + 1):
                        check_cmd = f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{vm_ip} 'sudo -n whoami' 2>&1"
                        result = subprocess.run(
                            check_cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )

                        if result.returncode == 0 and "root" in result.stdout:
                            if logger:
                                logger.log(f"✓ {vm_name} is ready")
                            vm_ready = True
                            # Clean SSH known_hosts
                            subprocess.run(
                                ["ssh-keygen", "-R", vm_ip], capture_output=True
                            )
                            break

                        if attempt < max_attempts:
                            time.sleep(10)

                    if not vm_ready:
                        if logger:
                            logger.warning(f"{vm_name} may not be fully ready")
                        all_ready = False

                if all_ready:
                    vm_count = len(public_ips)
                    # Create VM list with IPs: "app-0: 35.184.122.251, core-0: 34.41.132.41"
                    vm_list_with_ips = ", ".join(
                        [f"{name}: {ip}" for name, ip in sorted(public_ips.items())]
                    )
                    console.print("  [dim]✓ VMs ready[/dim]")
                else:
                    if logger:
                        logger.warning("Some VMs may not be fully ready, continuing...")
                    vm_count = len(public_ips)
                    # Create VM list with IPs even if not fully ready
                    vm_list_with_ips = ", ".join(
                        [f"{name}: {ip}" for name, ip in sorted(public_ips.items())]
                    )
                    console.print("  [yellow]⚠[/yellow] [dim]VMs partially ready[/dim]")

                # Show phase 1 completion with VM IPs
                console.print(
                    f"  [dim]✓ Configuration • Environment • {vm_count} VMs ({vm_list_with_ips})[/dim]"
                )
            else:
                if logger:
                    logger.log("No VMs found in outputs")

    else:
        # Skip terraform, load VMs from state
        from cli.state_manager import StateManager

        state_mgr = StateManager(project_root, project)
        state = state_mgr.load_state()
        vms = state.get("vms", {})

        if vms:
            vm_count = len(vms)
            # Build VM list with IPs from state
            vm_list_parts = []
            for vm_name, vm_data in sorted(vms.items()):
                external_ip = vm_data.get("external_ip", "no-ip")
                internal_ip = vm_data.get("internal_ip", "no-ip")
                vm_list_parts.append(f"{vm_name}-0: {external_ip}")

                # CRITICAL: Add IPs to env dict for inventory generation
                env[f"{vm_name.upper()}_0_EXTERNAL_IP"] = external_ip
                env[f"{vm_name.upper()}_0_INTERNAL_IP"] = internal_ip

            vm_list_with_ips = ", ".join(vm_list_parts)
            console.print(
                f"  [dim]✓ Configuration • Environment • {vm_count} VMs ({vm_list_with_ips})[/dim]"
            )
        else:
            console.print("  [dim]✓ Configuration • Environment loaded[/dim]")

    # Auto-update database secrets with VM internal IPs (for multi-VM architecture)
    ip_updater = SecretIPUpdater(project_root, project)
    ip_updater.update_secrets_with_vm_ips(env, logger)

    # Ansible - Smart skip logic
    if not skip_ansible:
        # Smart skip: if no ansible changes, skip it
        if changes and not changes.get("needs_ansible", True):
            if logger:
                logger.log("[dim]✓ Ansible: no addon/service changes, skipping[/dim]")
            skip_ansible = True
        else:
            if logger:
                logger.step("[2/4] Base System")

            # Load VM IPs from state if terraform was skipped
            if skip_terraform:
                from cli.state_manager import StateManager

                state_mgr = StateManager(project_root, project)
                state = state_mgr.load_state()

                # Extract VM IPs from state and add to env
                if "vms" in state:
                    for vm_role, vm_data in state["vms"].items():
                        # Add VM IPs in Terraform output format for inventory generation
                        # Format: {ROLE}_{INDEX}_EXTERNAL_IP and {ROLE}_{INDEX}_INTERNAL_IP
                        if "external_ip" in vm_data:
                            env[f"{vm_role.upper()}_0_EXTERNAL_IP"] = vm_data[
                                "external_ip"
                            ]
                        if "internal_ip" in vm_data:
                            env[f"{vm_role.upper()}_0_INTERNAL_IP"] = vm_data[
                                "internal_ip"
                            ]

                if logger:
                    logger.log("✓ VM IPs loaded from state")
            # else: env already has IPs from terraform outputs above

            # Generate inventory
            ansible_dir = project_root / "shared" / "ansible"
            inventory_generator = AnsibleInventoryGenerator(ansible_dir)
            inventory_generator.generate_inventory(
                env, project, orchestrator_ip, project_config_obj
            )

            # Build ansible command
            from cli.ansible_utils import build_ansible_command

            ansible_vars = project_config_obj.to_ansible_vars()
            ansible_vars["orchestrator_ip"] = orchestrator_ip

            # Load and pass database secrets to Ansible
            from cli.secret_manager import SecretManager

            secret_mgr = SecretManager(project_root, project, "production")
            all_secrets = secret_mgr.load_secrets()

            # Build secrets structure for Ansible (compatible with old format)
            secrets_dict = {
                "secrets": {
                    "shared": all_secrets.get("shared", {}),
                    "apps": all_secrets.get("apps", {}),
                    "addons": all_secrets.get("addons", {}),
                }
            }
            ansible_vars["project_secrets"] = secrets_dict

            # Get aliases from database
            from cli.database import get_db_session, SecretAlias

            alias_db = get_db_session()
            try:
                aliases = (
                    alias_db.query(SecretAlias)
                    .filter(SecretAlias.project_name == project)
                    .all()
                )
                env_aliases = {alias.alias_key: alias.target_key for alias in aliases}
            finally:
                alias_db.close()

            ansible_vars["env_aliases"] = env_aliases

            ansible_env_vars = {"superdeploy_root": str(project_root)}

            # Add VM IPs
            for key, value in env.items():
                if key.endswith("_EXTERNAL_IP") or key.endswith("_INTERNAL_IP"):
                    ansible_env_vars[key] = value
                    ansible_env_vars[key.lower()] = value

            # Determine ansible tags and enabled addons
            enabled_addons_list = None
            if addon:
                # Deploy only specific addon(s)
                enabled_addons_list = [a.strip() for a in addon.split(",")]
                ansible_tags = "addons"  # Only run addons tag
            elif tags:
                ansible_tags = tags
            else:
                # Smart foundation skip: if foundation already complete, skip it
                # BUT: always run foundation if --force flag is set
                tag_parts = []
                if force or (changes and changes.get("needs_foundation", True)):
                    tag_parts.append("foundation")
                else:
                    if logger:
                        logger.log(
                            "[dim]✓ Foundation: already complete, skipping[/dim]"
                        )

                tag_parts.extend(["addons", "project"])
                ansible_tags = ",".join(tag_parts)

            ansible_cmd = build_ansible_command(
                ansible_dir=ansible_dir,
                project_root=project_root,
                project_config=ansible_vars,
                env_vars=ansible_env_vars,
                tags=ansible_tags,
                project_name=project,
                ask_become_pass=False,
                enabled_addons=enabled_addons_list,
                force=force,
            )

            # Run ansible with clean tree view (or raw output if verbose)
            from cli.ansible_runner import AnsibleRunner

            runner = AnsibleRunner(
                logger, title="Configuring Services", verbose=verbose
            )

            # Track last runner for summary (default to main runner)
            last_runner = runner

            # Deploy addons separately for clean output (each addon as main-level play)
            deploy_addons_separately = "addons" in ansible_tags

            if deploy_addons_separately:
                # Get list of addons to deploy
                addons_to_deploy = enabled_addons_list if enabled_addons_list else []
                if not addons_to_deploy:
                    # Parse all addons from config
                    raw_addons = project_config_obj.raw_config.get("addons", {})
                    for category, instances in raw_addons.items():
                        for instance_name in instances.keys():
                            addons_to_deploy.append(f"{category}.{instance_name}")

            if deploy_addons_separately and addons_to_deploy:
                # Run foundation + project first (without addons)
                base_tags = (
                    ansible_tags.replace("addons,", "")
                    .replace(",addons", "")
                    .replace("addons", "")
                )
                if base_tags:
                    base_cmd = build_ansible_command(
                        ansible_dir=ansible_dir,
                        project_root=project_root,
                        project_config=ansible_vars,
                        env_vars=ansible_env_vars,
                        tags=base_tags,
                        project_name=project,
                        ask_become_pass=False,
                        enabled_addons=[],
                        force=force,
                    )
                    result_returncode = runner.run(base_cmd, cwd=project_root)

                    if result_returncode != 0:
                        if logger:
                            logger.log_error(
                                "Ansible configuration failed", context="Check logs"
                            )
                        raise SystemExit(1)

                # Deploy each addon separately for clean tree output
                last_runner = runner  # Track the last runner used
                for addon_name in addons_to_deploy:
                    # Parse addon (e.g., "databases.primary")
                    parts = addon_name.split(".")
                    if len(parts) != 2:
                        continue

                    category, instance_name = parts
                    addon_config = (
                        project_config_obj.raw_config.get("addons", {})
                        .get(category, {})
                        .get(instance_name, {})
                    )

                    if not addon_config:
                        continue

                    addon_type = addon_config.get("type")
                    addon_version = addon_config.get("version", "latest")
                    addon_plan = addon_config.get("plan", "standard")

                    # Build addon instance dict
                    addon_instance_dict = {
                        "full_name": addon_name,
                        "type": addon_type,
                        "version": addon_version,
                        "plan": addon_plan,
                        "category": category,
                        "name": instance_name,
                        "options": addon_config.get("options", {}),
                    }

                    # Determine target VM for addon
                    # Infrastructure addons (databases, queues, proxy) → core VMs
                    # Custom addons can specify vm in config
                    addon_vm = addon_config.get("vm")
                    if not addon_vm:
                        # Default mapping for infrastructure addons
                        if category in [
                            "databases",
                            "queues",
                            "proxy",
                            "cache",
                            "search",
                        ]:
                            addon_vm = "core"
                        else:
                            addon_vm = "all"  # Custom addons on all VMs by default

                    # Map VM selection to Ansible host pattern
                    if addon_vm == "core":
                        target_hosts = "core:!orchestrator"
                    elif addon_vm == "app":
                        target_hosts = "app:!orchestrator"
                    else:
                        target_hosts = "all:!orchestrator"

                    # Build addon-specific env vars (these get passed through to Ansible via custom_vars)
                    addon_env_vars = ansible_env_vars.copy()
                    addon_env_vars["addon_instance"] = addon_instance_dict
                    addon_env_vars["current_addon"] = (
                        addon_instance_dict  # For role compatibility
                    )
                    addon_env_vars["addons_base_path"] = (
                        f"/opt/superdeploy/projects/{project}/addons"
                    )
                    addon_env_vars["addons_source_path"] = str(
                        project_root / "shared" / "ansible" / "../../addons"
                    )
                    addon_env_vars["target_hosts"] = target_hosts

                    addon_cmd = build_ansible_command(
                        ansible_dir=ansible_dir,
                        project_root=project_root,
                        project_config=ansible_vars,  # Keep original config
                        env_vars=addon_env_vars,  # Pass addon vars via env_vars (gets added to custom_vars)
                        tags="",  # No tags for single addon
                        project_name=project,
                        ask_become_pass=False,
                        enabled_addons=[],
                        force=force,
                        playbook="addon-single.yml",  # Override playbook
                    )

                    addon_runner = AnsibleRunner(
                        logger, title=f"Deploy {addon_name}", verbose=verbose
                    )
                    result_returncode = addon_runner.run(addon_cmd, cwd=project_root)
                    last_runner = addon_runner  # Track the last addon runner

                    if result_returncode != 0:
                        if logger:
                            logger.log_error(f"Addon {addon_name} deployment failed")
                        raise SystemExit(1)
            else:
                # Normal single Ansible run
                result_returncode = runner.run(ansible_cmd, cwd=project_root)

                if result_returncode != 0:
                    if logger:
                        logger.log_error(
                            "Ansible configuration failed",
                            context="Check logs for details",
                        )
                    console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}")
                    console.print(
                        f"[dim]Ansible detailed log:[/dim] {logger.log_path.parent / f'{logger.log_path.stem}_ansible.log'}\n"
                    )
                    raise SystemExit(1)

            # Add summary to tree (use the last runner that was actually executed)
            if last_runner and last_runner.tree_renderer:
                last_runner.tree_renderer.add_summary_task(
                    "Services configured", "Services configured successfully"
                )

            # Update state: Mark deployment complete (VMs running, Ansible succeeded)
            from cli.state_manager import StateManager

            state_mgr = StateManager(project_root, project)

            # Mark foundation as complete (if foundation tag was run)
            if not tags or "foundation" in ansible_tags:
                state_mgr.mark_foundation_complete()

            # Mark each deployed addon
            if not tags or "addons" in ansible_tags:
                deployed_addons = enabled_addons_list or list(
                    project_config_obj.raw_config.get("addons", {}).keys()
                )
                for addon_name in deployed_addons:
                    state_mgr.mark_addon_deployed(addon_name)

            # Mark overall deployment as complete (VMs status: running)
            state_mgr.mark_deployment_complete()

    else:
        if logger:
            logger.step("Skipping Ansible (--skip-ansible)")

    # Phase 4: Code Deployment - Manual sync required
    # Note: Secret sync removed from automatic deployment due to timeout issues
    # User must manually run: superdeploy {project}:vars:sync

    # env already loaded at the beginning from database

    # Orchestrator info
    orchestrator_ip = env.get("ORCHESTRATOR_IP")
    if orchestrator_ip:
        if logger:
            logger.log("")
        if logger:
            logger.log("🎯 Orchestrator")
        if logger:
            logger.log(f"  IP: {orchestrator_ip}")

        # Get credentials from orchestrator secrets
        try:
            from cli.core.orchestrator_loader import OrchestratorLoader

            project_root = Path.cwd()
            orch_loader = OrchestratorLoader(project_root / "shared")
            orch_config = orch_loader.load()
            orch_secrets = orch_config.get_secrets()

            grafana_pass = orch_secrets.get("GRAFANA_ADMIN_PASSWORD", "")

            if logger:
                logger.log(f"  Grafana: http://{orchestrator_ip}:3000")
            if grafana_pass:
                if logger:
                    logger.log("    Username: admin")
                if logger:
                    logger.log(f"    Password: {grafana_pass}")

            if logger:
                logger.log(f"  Prometheus: http://{orchestrator_ip}:9090")
        except Exception:
            # Orchestrator config not available yet
            pass

    # Project VMs and Apps
    if logger:
        logger.log("")
    if logger:
        logger.log(f"📦 Project: {project}")

    # Get VM IPs
    vm_ips = {}
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP"):
            vm_name = key.replace("_EXTERNAL_IP", "").lower().replace("_", "-")
            vm_ips[vm_name] = value

    if vm_ips:
        if logger:
            logger.log("  VMs:")
        for vm_name, ip in sorted(vm_ips.items()):
            if logger:
                logger.log(f"    • {vm_name}: {ip}")

    # Display project credentials (postgres, rabbitmq, etc.)
    if logger:
        logger.log("")
    if logger:
        logger.log("🔐 Project Credentials")

    # PostgreSQL (from env vars set by addon deployment)
    postgres_host = env.get("POSTGRES_HOST", "")
    postgres_user = env.get("POSTGRES_USER", "")
    postgres_pass = env.get("POSTGRES_PASSWORD", "")
    postgres_db = env.get("POSTGRES_DB", "")

    if postgres_pass:
        if logger:
            logger.log("")
        if logger:
            logger.log("  🐘 PostgreSQL")
        if logger:
            logger.log(f"    Host: {postgres_host}")
        if logger:
            logger.log(f"    Database: {postgres_db}")
        if logger:
            logger.log(f"    Username: {postgres_user}")
        if logger:
            logger.log(f"    Password: {postgres_pass}")

    # RabbitMQ (from env vars set by addon deployment)
    rabbitmq_host = env.get("RABBITMQ_HOST", "")
    rabbitmq_user = env.get("RABBITMQ_USER") or env.get("RABBITMQ_DEFAULT_USER", "")
    rabbitmq_pass = env.get("RABBITMQ_PASSWORD") or env.get("RABBITMQ_DEFAULT_PASS", "")

    # Find core VM IP for RabbitMQ management UI
    core_vm_ip = None
    for vm_name, ip in vm_ips.items():
        if "core" in vm_name:
            core_vm_ip = ip
            break

    if rabbitmq_pass:
        if logger:
            logger.log("")
        if logger:
            logger.log("  🐰 RabbitMQ")
        if logger:
            logger.log(f"    Host: {rabbitmq_host}")
        if logger:
            logger.log(f"    Username: {rabbitmq_user}")
        if logger:
            logger.log(f"    Password: {rabbitmq_pass}")
        if core_vm_ip:
            if logger:
                logger.log(f"    Management UI: http://{core_vm_ip}:15672")

    # Redis (if exists)
    redis_host = env.get("REDIS_HOST", "")
    redis_pass = env.get("REDIS_PASSWORD", "")

    if redis_pass:
        if logger:
            logger.log("")
        if logger:
            logger.log("  📦 Redis")
        if logger:
            logger.log(f"    Host: {redis_host}")
        if logger:
            logger.log(f"    Password: {redis_pass}")

    # Get app URLs
    apps = project_config_obj.raw_config.get("apps", {})
    if apps:
        if logger:
            logger.log("")
        if logger:
            logger.log("  Applications:")
        for app_name, app_config in apps.items():
            domain = app_config.get("domain", "")
            port = app_config.get("port")
            vm_role = app_config.get("vm", "")

            # Find VM IP for this app
            vm_ip = None
            for vm_name, ip in vm_ips.items():
                if vm_role in vm_name:
                    vm_ip = ip
                    break

            if vm_ip:
                if domain:
                    if logger:
                        logger.log(f"    • {app_name}: https://{domain}")
                else:
                    if logger:
                        logger.log(f"    • {app_name}: http://{vm_ip}:{port}")

    # Display deployment success banner at the end
    if logger:
        logger.log("")
    if logger:
        logger.log("━" * 60)
    if logger:
        logger.success("Infrastructure Deployed!")
    if logger:
        logger.log("━" * 60)

    # Always display deployment summary (even in non-verbose mode)
    if not verbose:
        # Display deployment summary like orchestrator:up does
        console.print("\n" + "=" * 80)
        console.print(
            f"[bold cyan]🚀 {project.upper()} DEPLOYED SUCCESSFULLY[/bold cyan]"
        )
        console.print("=" * 80)

        # VMs
        if vm_ips:
            console.print(
                "\n[bold cyan]📍 Virtual Machines (External IPs):[/bold cyan]"
            )
            for vm_name, ip in sorted(vm_ips.items()):
                console.print(f"   • {vm_name}: [green]{ip}[/green]")

        # Orchestrator (if available)
        if orchestrator_ip:
            console.print("\n[bold cyan]🎯 Orchestrator:[/bold cyan]")
            console.print(f"   IP: {orchestrator_ip}")
            try:
                from cli.core.orchestrator_loader import OrchestratorLoader

                project_root = Path.cwd()
                orch_loader = OrchestratorLoader(project_root / "shared")
                orch_config = orch_loader.load()
                orch_secrets = orch_config.get_secrets()
                grafana_pass = orch_secrets.get("GRAFANA_ADMIN_PASSWORD", "")

                console.print(f"   📊 Grafana: http://{orchestrator_ip}:3000")
                if grafana_pass:
                    console.print("      Username: [bold]admin[/bold]")
                    console.print(f"      Password: [bold]{grafana_pass}[/bold]")
                console.print(f"   📈 Prometheus: http://{orchestrator_ip}:9090")
            except Exception:
                pass

        # Credentials
        console.print("\n[bold cyan]🔐 Access Credentials:[/bold cyan]")

        # PostgreSQL
        if postgres_pass:
            console.print("\n[cyan]🐘 PostgreSQL:[/cyan]")
            console.print(f"   Host: [bold]{postgres_host}[/bold]")
            console.print(f"   Database: [bold]{postgres_db}[/bold]")
            console.print(f"   Username: [bold]{postgres_user}[/bold]")
            console.print(f"   Password: [bold]{postgres_pass}[/bold]")

        # RabbitMQ
        if rabbitmq_pass:
            console.print("\n[cyan]🐰 RabbitMQ:[/cyan]")
            console.print(f"   Host: [bold]{rabbitmq_host}[/bold]")
            console.print(f"   Username: [bold]{rabbitmq_user}[/bold]")
            console.print(f"   Password: [bold]{rabbitmq_pass}[/bold]")
            if core_vm_ip:
                console.print(f"   Management UI: http://{core_vm_ip}:15672")

        # Redis (if exists)
        if redis_pass:
            console.print("\n[cyan]📦 Redis:[/cyan]")
            console.print(f"   Host: [bold]{redis_host}[/bold]")
            console.print(f"   Password: [bold]{redis_pass}[/bold]")

        # Applications
        if apps:
            console.print("\n[bold cyan]🌐 Applications:[/bold cyan]")
            for app_name, app_config in apps.items():
                domain = app_config.get("domain", "")
                port = app_config.get("port")
                vm_role = app_config.get("vm", "")

                # Find VM IP for this app
                vm_ip = None
                for vm_name, ip in vm_ips.items():
                    if vm_role in vm_name:
                        vm_ip = ip
                        break

                if vm_ip:
                    if domain:
                        console.print(f"   • [cyan]{app_name}:[/cyan] https://{domain}")
                    elif port:
                        console.print(
                            f"   • [cyan]{app_name}:[/cyan] http://{vm_ip}:{port}"
                        )
                    else:
                        # Worker or internal service (no public endpoint)
                        console.print(
                            f"   • [cyan]{app_name}:[/cyan] [dim](worker - no public endpoint)[/dim]"
                        )

        # Important next step: Secret sync
        console.print(
            "\n[bold yellow]⚠️  IMPORTANT: Sync secrets to GitHub[/bold yellow]"
        )
        console.print(f"   Run: [bold cyan]superdeploy {project}:vars:sync[/bold cyan]")
        console.print(
            "   [dim]This syncs your secrets to GitHub for CI/CD workflows[/dim]"
        )

        console.print("\n" + "=" * 80)
        console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}")
        console.print(
            f"[dim]Ansible detailed log:[/dim] {logger.log_path.parent / f'{logger.log_path.stem}_ansible.log'}\n"
        )


# Click command wrapper
@click.command()
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
@click.option("--addon", help="Deploy only specific addon(s), comma-separated")
@click.option("--tags", help="Run only specific Ansible tags")
@click.option("--preserve-ip", is_flag=True, help="Preserve existing static IPs")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--force", is_flag=True, help="Force update (ignore state)")
@click.option("--dry-run", is_flag=True, help="Show what would be done (like plan)")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def up(
    project,
    skip_terraform,
    skip_ansible,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
    force,
    dry_run,
    json_output,
):
    """Deploy infrastructure (like 'heroku create')"""
    cmd = UpCommand(
        project_name=project,
        skip_terraform=skip_terraform,
        skip_ansible=skip_ansible,
        skip=skip,
        addon=addon,
        tags=tags,
        preserve_ip=preserve_ip,
        verbose=verbose,
        force=force,
        dry_run=dry_run,
        json_output=json_output,
    )
    cmd.run()
