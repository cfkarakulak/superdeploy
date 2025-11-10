"""SuperDeploy CLI - Up command (with smart deployment and change detection)"""

import click
import subprocess
from pathlib import Path
from cli.base import ProjectCommand
from cli.logger import DeployLogger, run_with_progress


class UpCommand(ProjectCommand):
    """Deploy project infrastructure."""

    def __init__(
        self,
        project_name: str,
        skip_terraform: bool = False,
        skip_ansible: bool = False,
        skip_sync: bool = False,
        skip: tuple = (),
        addon: str = None,
        tags: str = None,
        preserve_ip: bool = False,
        verbose: bool = False,
        force: bool = False,
        dry_run: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.skip_terraform = skip_terraform
        self.skip_ansible = skip_ansible
        self.skip_sync = skip_sync
        self.skip = skip
        self.addon = addon
        self.tags = tags
        self.preserve_ip = preserve_ip
        self.force = force
        self.dry_run = dry_run

    def execute(self) -> None:
        """Execute up command."""
        self._execute_deployment()

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
                # Validate secrets before deployment
                validation_errors = _validate_secrets(
                    self.project_root, self.config_service, self.project_name, logger
                )
                if validation_errors:
                    self.console.print("")
                    self.console.print("[red]❌ Validation Failed[/red]")
                    self.console.print("")
                    self.console.print("Please fix the following issues:")
                    self.console.print("")
                    for error in validation_errors:
                        self.console.print(f"  [red]•[/red] {error}")
                    self.console.print("")
                    self.console.print(
                        "[dim]Edit secrets:[/dim] projects/{}/secrets.yml".format(
                            self.project_name
                        )
                    )
                    self.console.print("")
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
                        logger.log("🗑️  State cleared (force mode)")
                        logger.log("")

                # Change detection (smart deployment)
                changes = None  # Initialize - will be set if change detection runs

                # Force mode or skip flags - no change detection
                if self.force or self.skip_terraform or self.skip_ansible:
                    # Force mode: Skip change detection, deploy everything
                    if self.force:
                        logger.log("🔄 Force mode: skipping change detection")
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
                        logger.log_error(f"Project not found: {self.project_name}")
                        raise SystemExit(1)
                    except ValueError as e:
                        logger.log_error(f"Invalid configuration: {e}")
                        raise SystemExit(1)

                    # Detect changes
                    state_mgr = StateManager(self.project_root, self.project_name)
                    changes, state = state_mgr.detect_changes(project_config)

                    # Dry-run mode
                    if self.dry_run:
                        logger.log("🔍 Dry-run mode: showing what would be done")
                        logger.log("")

                        if not changes["has_changes"]:
                            logger.success(
                                "✅ No changes detected. Infrastructure is up to date."
                            )
                            return

                        # Show changes (mini plan)
                        if changes["vms"]["added"]:
                            logger.log(
                                f"VMs to create: {', '.join(changes['vms']['added'])}"
                            )
                        if changes["vms"]["modified"]:
                            modified_vms = [
                                v["name"] for v in changes["vms"]["modified"]
                            ]
                            logger.log(f"VMs to modify: {', '.join(modified_vms)}")
                        if changes["addons"]["added"]:
                            logger.log(
                                f"Addons to install: {', '.join(changes['addons']['added'])}"
                            )
                        if changes["apps"]["added"]:
                            logger.log(
                                f"Apps to setup: {', '.join(changes['apps']['added'])}"
                            )

                        logger.log("")
                        logger.log("Run without --dry-run to apply changes")
                        return

                    # No changes - skip deployment
                    if not changes["has_changes"]:
                        logger.log("🔍 Detecting changes...")
                        logger.log("")
                        logger.success("✅ No changes detected.")
                        logger.log("")
                        logger.log("Infrastructure is up to date with config.yml")
                        logger.log("")
                        logger.log(
                            f"To force update: superdeploy {self.project_name}:up --force"
                        )
                        return

                    # Show detected changes
                    logger.log("🔍 Detecting changes...")
                    logger.log("")

                    # Check if any VMs need configuration
                    state = state_mgr.load_state()
                    vms_needing_config = []
                    for vm_name, vm_data in state.get("vms", {}).items():
                        if vm_data.get("status") == "provisioned":
                            vms_needing_config.append(vm_name)

                    if vms_needing_config:
                        logger.log(
                            f"  [yellow]⚙ VMs need configuration:[/yellow] {', '.join(vms_needing_config)}"
                        )

                    if changes["vms"]["added"]:
                        logger.log(
                            f"  [green]+ VMs to create:[/green] {', '.join(changes['vms']['added'])}"
                        )
                    if changes["vms"]["modified"]:
                        modified_vms = [v["name"] for v in changes["vms"]["modified"]]
                        logger.log(
                            f"  [yellow]~ VMs to modify:[/yellow] {', '.join(modified_vms)}"
                        )
                    if changes["addons"]["added"]:
                        logger.log(
                            f"  [green]+ Addons to install:[/green] {', '.join(changes['addons']['added'])}"
                        )
                    if changes["apps"]["added"]:
                        logger.log(
                            f"  [green]+ Apps to setup:[/green] {', '.join(changes['apps']['added'])}"
                        )

                    logger.log("")
                    logger.log("Proceeding with deployment...")
                    logger.log("")

                    # Override skip flags based on what's needed
                    if not changes["needs_terraform"]:
                        self.skip_terraform = True
                        logger.log(
                            "  [dim]⏭ Skipping Terraform (no infrastructure changes)[/dim]"
                        )

                    if not changes["needs_ansible"]:
                        self.skip_ansible = True
                        logger.log(
                            "  [dim]⏭ Skipping Ansible (no service changes)[/dim]"
                        )

                    if not changes["needs_sync"]:
                        self.skip_sync = True
                        logger.log("  [dim]⏭ Skipping sync (no new secrets)[/dim]")

                    # Auto-generate workflows if needed
                    if changes["needs_generate"]:
                        logger.log("  [cyan]→ Auto-generating workflows...[/cyan]")

                        # Use subprocess to call generate with namespace syntax
                        import sys

                        generate_cmd = [
                            sys.executable,
                            "-m",
                            "cli.main",
                            f"{self.project_name}:generate",
                        ]

                        result = subprocess.run(
                            generate_cmd,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )

                        if result.returncode != 0:
                            logger.log_error("Workflow generation failed")
                            if result.stderr:
                                for line in result.stderr.split("\n")[:5]:
                                    if line.strip():
                                        logger.warn(f"  {line}")
                            raise SystemExit(1)

                        logger.log("  [dim]✓ Workflows generated[/dim]")

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

                    logger.log("")
                    logger.log("💾 State saved")

            except Exception as e:
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
            self.skip_sync,
            self.skip,
            self.addon,
            self.tags,
            self.preserve_ip,
            self.verbose,
            self.force,
            changes,
        )


def _deploy_project_internal(
    logger,
    console,
    project_root,
    config_service,
    project,
    skip_terraform,
    skip_ansible,
    skip_sync,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
    force,
    changes=None,  # For smart skip logic
):
    """Internal function for project deployment with logging"""

    logger.step("[1/4] Setup & Infrastructure")

    # Load project config
    from cli.core.orchestrator_loader import OrchestratorLoader

    shared_dir = project_root / "shared"

    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        project_config_obj = config_service.load_project_config(project)
        console.print("  [dim]✓ Configuration loaded[/dim]")
    except FileNotFoundError as e:
        logger.log_error(str(e), context=f"Project '{project}' not found")
        raise SystemExit(1)
    except ValueError as e:
        logger.log_error(f"Invalid configuration: {e}")
        raise SystemExit(1)

    # Load orchestrator config
    try:
        orchestrator_config = orchestrator_loader.load()

        # Check if orchestrator is deployed
        if not orchestrator_config.is_deployed():
            logger.log_error(
                "Orchestrator not deployed yet",
                context="Deploy it first: [red]superdeploy orchestrator up[/red]",
            )
            raise SystemExit(1)

        orchestrator_ip = orchestrator_config.get_ip()
        if not orchestrator_ip:
            logger.log_error("Orchestrator IP not found")
            raise SystemExit(1)

        console.print(f"  [dim]✓ Orchestrator @ {orchestrator_ip}[/dim]")

    except FileNotFoundError as e:
        logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Load project config and environment
    from cli.utils import validate_env_vars
    from cli.secret_manager import SecretManager

    project_dir = project_root / "projects" / project

    # Load project config (using config_service from parameter)
    project_config_obj = config_service.load_project_config(project)

    # Load from secrets.yml instead of .env
    secret_mgr = SecretManager(project_root, project)
    secrets_data = secret_mgr.load_secrets()

    # Build env dict from config.yml + secrets.yml
    env = {
        "GCP_PROJECT_ID": project_config_obj.raw_config["cloud"]["gcp"]["project_id"],
        "GCP_REGION": project_config_obj.raw_config["cloud"]["gcp"]["region"],
        "SSH_KEY_PATH": project_config_obj.raw_config["cloud"]["ssh"]["key_path"],
        "SSH_USER": project_config_obj.raw_config["cloud"]["ssh"]["user"],
    }

    # Add secrets to env
    if secrets_data.get("secrets", {}).get("shared"):
        env.update(secrets_data["secrets"]["shared"])

    # Validate required vars
    required = ["GCP_PROJECT_ID", "GCP_REGION", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        logger.log_error(
            "Missing required environment variables", context=", ".join(required)
        )
        raise SystemExit(1)

    logger.log("✓ Environment validated")

    # Terraform - Smart skip logic
    if not skip_terraform:
        # Smart skip: if no terraform changes, skip it
        if changes and not changes.get("needs_terraform", True):
            logger.log("[dim]✓ Terraform: no VM changes, skipping[/dim]")
            skip_terraform = True
        else:
            logger.log("Provisioning VMs (3-5 min)...")

            from cli.terraform_utils import (
                terraform_refresh,
                generate_tfvars,
            )

            # Ensure we're on default workspace before init (prevents interactive prompt)
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

            # Add IPs to env dict for Ansible
            for vm_key, ip in sorted(public_ips.items()):
                env_key = vm_key.upper().replace("-", "_")
                env[f"{env_key}_EXTERNAL_IP"] = ip

            for vm_key, ip in sorted(internal_ips.items()):
                env_key = vm_key.upper().replace("-", "_")
                env[f"{env_key}_INTERNAL_IP"] = ip

            logger.log("✓ VM IPs loaded to environment")

            # Wait for VMs
            logger.log("Waiting for VMs to be ready...")

            if public_ips:
                import time

                ssh_key = env.get("SSH_KEY_PATH")
                ssh_user = env.get("SSH_USER", "superdeploy")

                # Check each VM
                max_attempts = 18
                all_ready = True

                for vm_name, vm_ip in public_ips.items():
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

    # Auto-update secrets.yml with VM internal IPs (for multi-VM architecture)
    _update_secrets_with_vm_ips(project_root, project, env, logger)

    # Ansible - Smart skip logic
    if not skip_ansible:
        # Smart skip: if no ansible changes, skip it
        if changes and not changes.get("needs_ansible", True):
            logger.log("[dim]✓ Ansible: no addon/service changes, skipping[/dim]")
            skip_ansible = True
        else:
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

                logger.log("✓ VM IPs loaded from state")
            # else: env already has IPs from terraform outputs above

            # Generate inventory
            from cli.commands.up import generate_ansible_inventory

            ansible_dir = project_root / "shared" / "ansible"
            generate_ansible_inventory(
                env, ansible_dir, project, orchestrator_ip, project_config_obj
            )

            # Build ansible command
            from cli.ansible_utils import build_ansible_command

            ansible_vars = project_config_obj.to_ansible_vars()
            ansible_vars["orchestrator_ip"] = orchestrator_ip

            # Load and pass secrets.yml to Ansible
            from cli.secret_manager import SecretManager

            secret_mgr = SecretManager(project_root, project)
            all_secrets = secret_mgr.load_secrets()
            ansible_vars["project_secrets"] = all_secrets.get("secrets", {})
            ansible_vars["env_aliases"] = all_secrets.get("env_aliases", {})

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
                tag_parts = []
                if changes and changes.get("needs_foundation", True):
                    tag_parts.append("foundation")
                else:
                    logger.log("[dim]✓ Foundation: already complete, skipping[/dim]")

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

            console.print("[green]✓ Services configured[/green]")

            logger.success("Services configured successfully")

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
        logger.step("Skipping Ansible (--skip-ansible)")

    # Phase 4: Code Deployment
    if not skip_sync:
        logger.step("[4/4] Code Deployment")

    # Sync secrets to GitHub
    if not skip_sync and not skip_ansible:
        logger.log("Syncing secrets to GitHub...")
        try:
            # Call sync command programmatically
            # Note: CliRunner with namespace commands doesn't work well
            # Use subprocess to call the actual CLI with namespace syntax
            import sys

            sync_cmd = [
                sys.executable,
                "-m",
                "cli.main",
                f"{project}:sync",
            ]

            try:
                result = subprocess.run(
                    sync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0:
                    logger.log("✓ Secrets synced to GitHub")
                else:
                    logger.warn("⚠ Secret sync had issues:")
                    if result.stderr:
                        for line in result.stderr.split("\n")[:5]:
                            if line.strip():
                                logger.warn(f"  {line}")
            except subprocess.TimeoutExpired:
                logger.warn("⚠ Secret sync timed out")
            except Exception as e:
                logger.warn(f"⚠ Secret sync failed: {e}")
        except Exception as e:
            logger.log_error(f"Failed to sync secrets: {e}")
            logger.warning("Continuing deployment without secret sync")

    # env already loaded at the beginning from secrets.yml

    # Orchestrator info
    orchestrator_ip = env.get("ORCHESTRATOR_IP")
    if orchestrator_ip:
        logger.log("")
        logger.log("🎯 Orchestrator")
        logger.log(f"  IP: {orchestrator_ip}")

        # Get credentials from orchestrator secrets
        try:
            from cli.core.orchestrator_loader import OrchestratorLoader

            project_root = Path.cwd()
            orch_loader = OrchestratorLoader(project_root / "shared")
            orch_config = orch_loader.load()
            orch_secrets = orch_config.get_secrets()

            grafana_pass = orch_secrets.get("GRAFANA_ADMIN_PASSWORD", "")

            logger.log(f"  Grafana: http://{orchestrator_ip}:3000")
            if grafana_pass:
                logger.log("    Username: admin")
                logger.log(f"    Password: {grafana_pass}")

            logger.log(f"  Prometheus: http://{orchestrator_ip}:9090")
        except Exception:
            # Orchestrator config not available yet
            pass

    # Project VMs and Apps
    logger.log("")
    logger.log(f"📦 Project: {project}")

    # Get VM IPs
    vm_ips = {}
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP"):
            vm_name = key.replace("_EXTERNAL_IP", "").lower().replace("_", "-")
            vm_ips[vm_name] = value

    if vm_ips:
        logger.log("  VMs:")
        for vm_name, ip in sorted(vm_ips.items()):
            logger.log(f"    • {vm_name}: {ip}")

    # Display project credentials (postgres, rabbitmq, etc.)
    logger.log("")
    logger.log("🔐 Project Credentials")

    # PostgreSQL
    postgres_host = env.get("POSTGRES_HOST") or project_config_obj.raw_config.get(
        "addons", {}
    ).get("postgres", {}).get("host", "postgres")
    postgres_user = env.get("POSTGRES_USER") or project_config_obj.raw_config.get(
        "addons", {}
    ).get("postgres", {}).get("user", f"{project}_user")
    postgres_pass = env.get("POSTGRES_PASSWORD", "")
    postgres_db = env.get("POSTGRES_DB") or project_config_obj.raw_config.get(
        "addons", {}
    ).get("postgres", {}).get("database", f"{project}_db")

    if postgres_pass:
        logger.log("")
        logger.log("  🐘 PostgreSQL")
        logger.log(f"    Host: {postgres_host}")
        logger.log(f"    Database: {postgres_db}")
        logger.log(f"    Username: {postgres_user}")
        logger.log(f"    Password: {postgres_pass}")

    # RabbitMQ
    rabbitmq_host = env.get("RABBITMQ_HOST") or project_config_obj.raw_config.get(
        "addons", {}
    ).get("rabbitmq", {}).get("host", "rabbitmq")
    rabbitmq_user = (
        env.get("RABBITMQ_USER")
        or env.get("RABBITMQ_DEFAULT_USER")
        or project_config_obj.raw_config.get("addons", {})
        .get("rabbitmq", {})
        .get("user", f"{project}_user")
    )
    rabbitmq_pass = env.get("RABBITMQ_PASSWORD") or env.get("RABBITMQ_DEFAULT_PASS", "")

    # Find core VM IP for RabbitMQ management UI
    core_vm_ip = None
    for vm_name, ip in vm_ips.items():
        if "core" in vm_name:
            core_vm_ip = ip
            break

    if rabbitmq_pass:
        logger.log("")
        logger.log("  🐰 RabbitMQ")
        logger.log(f"    Host: {rabbitmq_host}")
        logger.log(f"    Username: {rabbitmq_user}")
        logger.log(f"    Password: {rabbitmq_pass}")
        if core_vm_ip:
            logger.log(f"    Management UI: http://{core_vm_ip}:15672")

    # Redis (if exists)
    redis_host = env.get("REDIS_HOST", "")
    redis_pass = env.get("REDIS_PASSWORD", "")

    if redis_pass:
        logger.log("")
        logger.log("  📦 Redis")
        logger.log(f"    Host: {redis_host}")
        logger.log(f"    Password: {redis_pass}")

    # Get app URLs
    apps = project_config_obj.raw_config.get("apps", {})
    if apps:
        logger.log("")
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
                    logger.log(f"    • {app_name}: https://{domain}")
                else:
                    logger.log(f"    • {app_name}: http://{vm_ip}:{port}")

    # Display deployment success banner at the end
    logger.log("")
    logger.log("━" * 60)
    logger.success("Infrastructure Deployed!")
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
                    else:
                        console.print(
                            f"   • [cyan]{app_name}:[/cyan] http://{vm_ip}:{port}"
                        )

        console.print("\n" + "=" * 80)
        console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}")
        console.print(
            f"[dim]Ansible detailed log:[/dim] {logger.log_path.parent / f'{logger.log_path.stem}_ansible.log'}\n"
        )


def generate_ansible_inventory(
    env, ansible_dir, project_name, orchestrator_ip=None, project_config=None
):
    """Generate Ansible inventory file dynamically from environment variables

    Args:
        env: Environment variables dict
        ansible_dir: Path to ansible directory
        project_name: Project name
        orchestrator_ip: Orchestrator VM IP (from global config)
        project_config: Project configuration object (to get VM services)
    """
    import json

    # Extract VM groups from environment variables
    # Format: {ROLE}_{INDEX}_EXTERNAL_IP
    vm_groups = {}

    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP"):
            # Parse VM key from env var (e.g., "CORE_0_EXTERNAL_IP" -> "core-0")
            vm_key = key.replace("_EXTERNAL_IP", "").lower().replace("_", "-")
            # Extract role from vm_key (e.g., "core-0" -> "core")
            role = vm_key.rsplit("-", 1)[0]

            if role not in vm_groups:
                vm_groups[role] = []

            vm_info = {
                "name": f"{project_name}-{vm_key}",
                "host": value,
                "user": env.get("SSH_USER", "superdeploy"),
                "role": role,
            }

            vm_groups[role].append(vm_info)

    # Get VM services and apps from project config
    vm_services_map = {}
    vm_apps_map = {}

    if project_config:
        vms_config = project_config.raw_config.get("vms", {})
        apps_config = project_config.raw_config.get("apps", {})

        # Build services map per VM
        for vm_role, vm_def in vms_config.items():
            services = list(vm_def.get("services", []))  # Make a copy

            # Always add caddy to every VM (for domain management and reverse proxy)
            if "caddy" not in services:
                services.append("caddy")

            vm_services_map[vm_role] = services

        # Build apps map per VM (which apps are assigned to which VM)
        for app_name, app_config in apps_config.items():
            app_vm = app_config.get("vm", "app")  # Default to 'app' VM
            if app_vm not in vm_apps_map:
                vm_apps_map[app_vm] = []
            vm_apps_map[app_vm].append(app_name)

    # Build inventory content
    inventory_lines = []

    # NOTE: Orchestrator is included in inventory for runner registration
    # but it won't receive project-specific addons (filtered by vm_services)

    # Add orchestrator group if available (for runner token generation)
    if orchestrator_ip:
        inventory_lines.append("[orchestrator]")
        inventory_lines.append(
            f"orchestrator-main-0 ansible_host={orchestrator_ip} ansible_user=superdeploy vm_role=orchestrator"
        )
        inventory_lines.append("")

    # Add project VM groups
    for role in sorted(vm_groups.keys()):
        inventory_lines.append(f"[{role}]")
        for vm in sorted(vm_groups[role], key=lambda x: x["name"]):
            # Get services for this VM role
            services = vm_services_map.get(role, [])
            # Get apps for this VM role
            apps = vm_apps_map.get(role, [])

            # Convert to JSON and properly quote for INI format
            # INI parser needs quotes around JSON arrays
            services_json = json.dumps(services).replace('"', '\\"')
            apps_json = json.dumps(apps).replace('"', '\\"')

            inventory_lines.append(
                f'{vm["name"]} ansible_host={vm["host"]} ansible_user={vm["user"]} vm_role={role} vm_services="{services_json}" vm_apps="{apps_json}"'
            )
        inventory_lines.append("")  # Empty line between groups

    inventory_content = "\n".join(inventory_lines)

    inventory_path = ansible_dir / "inventories" / f"{project_name}.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)


def _validate_secrets(project_root, config_service, project_name, logger):
    """
    Validate project secrets before deployment.

    Returns:
        List of error messages (empty list if validation passes)
    """
    from cli.secret_manager import SecretManager

    errors = []

    # Initialize secret manager
    secret_mgr = SecretManager(project_root, project_name)

    # Check if secrets file exists
    if not secret_mgr.secrets_file.exists():
        errors.append("secrets.yml not found")
        errors.append(f"Run: superdeploy :init{project_name}")
        return errors

    # Load secrets
    try:
        secrets_data = secret_mgr.load_secrets()
    except Exception as e:
        errors.append(f"Failed to load secrets.yml: {e}")
        return errors

    if not secrets_data or "secrets" not in secrets_data:
        errors.append("Invalid secrets.yml structure (missing 'secrets' key)")
        return errors

    shared_secrets = secrets_data["secrets"].get("shared", {})

    # Required: Docker credentials
    docker_username = shared_secrets.get("DOCKER_USERNAME", "").strip()
    docker_token = shared_secrets.get("DOCKER_TOKEN", "").strip()

    if not docker_username:
        errors.append("DOCKER_USERNAME is missing or empty in secrets.yml")
    if not docker_token:
        errors.append("DOCKER_TOKEN is missing or empty in secrets.yml")

    # Required: GitHub token (for CI/CD)
    github_token = shared_secrets.get("GITHUB_TOKEN", "").strip()
    if not github_token:
        errors.append("GITHUB_TOKEN is missing or empty in secrets.yml")

    # Warn about ORCHESTRATOR_IP (should be set after orchestrator:up)
    orchestrator_ip = shared_secrets.get("ORCHESTRATOR_IP", "").strip()
    if not orchestrator_ip:
        logger.log("")
        logger.log("[yellow]⚠[/yellow] ORCHESTRATOR_IP not set in secrets.yml")
        logger.log(
            "[dim]   Run 'superdeploy orchestrator:up' first to set it automatically[/dim]"
        )
        logger.log("")

    # Addon-specific validation: Check required secrets for enabled addons
    try:
        import yaml

        project_config = config_service.load_project_config(project_name)

        # Get enabled addons
        enabled_addons = project_config.raw_config.get("addons", {})

        if enabled_addons:
            addons_dir = project_root / "addons"

            for addon_name in enabled_addons.keys():
                addon_yml_path = addons_dir / addon_name / "addon.yml"

                if not addon_yml_path.exists():
                    continue  # Skip if addon.yml not found

                # Load addon metadata
                try:
                    with open(addon_yml_path, "r") as f:
                        addon_meta = yaml.safe_load(f)

                    # Check for required secret env vars
                    env_vars = addon_meta.get("env_vars", [])

                    for env_var in env_vars:
                        var_name = env_var.get("name")
                        is_secret = env_var.get("secret", False)
                        is_required = env_var.get("required", False)

                        # Only validate required secrets
                        if is_secret and is_required:
                            var_value = shared_secrets.get(var_name, "").strip()

                            if not var_value:
                                errors.append(
                                    f"{var_name} is missing or empty (required by {addon_name} addon)"
                                )

                except Exception as e:
                    # Don't fail validation if addon.yml parsing fails
                    logger.log(
                        f"[dim]Warning: Could not parse addon.yml for {addon_name}: {e}[/dim]"
                    )

    except Exception as e:
        # Don't fail validation if project config loading fails
        logger.log(
            f"[dim]Warning: Could not load project config for addon validation: {e}[/dim]"
        )

    return errors


def _update_secrets_with_vm_ips(project_root, project, env, logger):
    """
    Auto-update secrets.yml with VM internal IPs for multi-VM architecture

    This ensures services like postgres/rabbitmq on core VM can be reached
    from apps on app VM using internal IPs instead of hostnames.
    """
    from cli.secret_manager import SecretManager
    from cli.state_manager import StateManager

    secret_mgr = SecretManager(project_root, project)
    secrets_data = secret_mgr.load_secrets()

    if not secrets_data or "secrets" not in secrets_data:
        return  # No secrets to update

    shared_secrets = secrets_data.get("secrets", {}).get("shared", {})
    if not shared_secrets:
        return  # No shared secrets

    # Get core VM internal IP from env or state
    core_internal_ip = env.get("CORE_0_INTERNAL_IP")

    if not core_internal_ip:
        # Try to load from state
        state_mgr = StateManager(project_root, project)
        state = state_mgr.load_state()
        core_vm = state.get("vms", {}).get("core", {})
        core_internal_ip = core_vm.get("internal_ip")

    if not core_internal_ip:
        return  # No core VM found

    # Update service hosts with internal IP
    updated = False
    service_hosts = {
        "POSTGRES_HOST": ("postgres", "PostgreSQL"),
        "RABBITMQ_HOST": ("rabbitmq", "RabbitMQ"),
        "MONGODB_HOST": ("mongodb", "MongoDB"),
        "REDIS_HOST": ("redis", "Redis"),
        "ELASTICSEARCH_HOST": ("elasticsearch", "Elasticsearch"),
    }

    for host_key, (default_name, service_name) in service_hosts.items():
        if host_key in shared_secrets:
            current_value = shared_secrets[host_key]
            # Update if it's default hostname OR if it differs from core IP
            if current_value != core_internal_ip:
                old_value = current_value
                shared_secrets[host_key] = core_internal_ip
                updated = True
                logger.log(
                    f"  [dim]✓ Updated {service_name} host: {old_value} → {core_internal_ip}[/dim]"
                )

    if updated:
        # Save updated secrets
        secrets_data["secrets"]["shared"] = shared_secrets
        secret_mgr.save_secrets(secrets_data)
        logger.log("  [dim]✓ secrets.yml updated with VM internal IPs[/dim]")


# Click command wrapper
@click.command()
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
@click.option("--addon", help="Deploy only specific addon(s), comma-separated")
@click.option("--tags", help="Run only specific Ansible tags")
@click.option("--preserve-ip", is_flag=True, help="Preserve existing static IPs")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--force", is_flag=True, help="Force update (ignore state)")
@click.option("--dry-run", is_flag=True, help="Show what would be done (like plan)")
def up(
    project,
    skip_terraform,
    skip_ansible,
    skip_sync,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
    force,
    dry_run,
):
    """Deploy infrastructure (like 'heroku create')"""
    cmd = UpCommand(
        project_name=project,
        skip_terraform=skip_terraform,
        skip_ansible=skip_ansible,
        skip_sync=skip_sync,
        skip=skip,
        addon=addon,
        tags=tags,
        preserve_ip=preserve_ip,
        verbose=verbose,
        force=force,
        dry_run=dry_run,
    )
    cmd.run()
