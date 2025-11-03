"""SuperDeploy CLI - Up command V2 (with improved logging and UX)"""

import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from cli.logger import DeployLogger, run_with_progress

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-git-push", is_flag=True, help="Skip Git push")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
@click.option("--addon", help="Deploy only specific addon(s), comma-separated")
@click.option("--tags", help="Run only specific Ansible tags")
@click.option("--preserve-ip", is_flag=True, help="Preserve existing static IPs")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def up(
    project,
    skip_terraform,
    skip_ansible,
    skip_git_push,
    skip_sync,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
):
    """
    Deploy infrastructure (like 'heroku create')

    This command will:
    - Provision VMs with Terraform
    - Configure services with Ansible
    - Push code to Forgejo
    - Setup Forgejo runner
    """

    if not verbose:
        console.print(
            Panel.fit(
                f"[bold cyan]🚀 SuperDeploy Infrastructure Deployment[/bold cyan]\n\n"
                f"[white]Deploying project: [bold]{project}[/bold][/white]",
                border_style="cyan",
            )
        )

    from cli.utils import get_project_root

    project_root = get_project_root()

    # Initialize logger
    with DeployLogger(project, "up", verbose=verbose) as logger:
        try:
            _deploy_project_v2(
                logger,
                project_root,
                project,
                skip_terraform,
                skip_ansible,
                skip_git_push,
                skip_sync,
                skip,
                addon,
                tags,
                preserve_ip,
                verbose,
            )

            if not verbose:
                console.print(
                    "\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]"
                )
                console.print("[bold green]✅ Infrastructure Deployed![/bold green]")
                console.print(
                    "[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]\n"
                )

        except Exception as e:
            logger.log_error(str(e), context=f"Project {project} deployment failed")
            raise SystemExit(1)


def _deploy_project_v2(
    logger,
    project_root,
    project,
    skip_terraform,
    skip_ansible,
    skip_git_push,
    skip_sync,
    skip,
    addon,
    tags,
    preserve_ip,
    verbose,
):
    """Internal function for project deployment with logging"""

    # Load project config
    logger.step("Loading project configuration")
    from cli.core.config_loader import ConfigLoader
    from cli.core.orchestrator_loader import OrchestratorLoader

    projects_dir = project_root / "projects"
    shared_dir = project_root / "shared"

    config_loader = ConfigLoader(projects_dir)
    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        project_config_obj = config_loader.load_project(project)
        logger.success("Project configuration loaded")
    except FileNotFoundError as e:
        logger.log_error(str(e), context=f"Project '{project}' not found")
        raise SystemExit(1)
    except ValueError as e:
        logger.log_error(f"Invalid configuration: {e}")
        raise SystemExit(1)

    # Load orchestrator config
    logger.log("Loading orchestrator configuration")
    try:
        orchestrator_config = orchestrator_loader.load()
        logger.log("Orchestrator configuration loaded")

        # Check if orchestrator is deployed
        if not orchestrator_config.is_deployed():
            logger.log_error(
                "Orchestrator not deployed yet",
                context="Deploy it first: superdeploy orchestrator up",
            )
            raise SystemExit(1)

        orchestrator_ip = orchestrator_config.get_ip()
        if not orchestrator_ip:
            logger.log_error("Orchestrator IP not found")
            raise SystemExit(1)

        logger.log(f"Using orchestrator: {orchestrator_ip}")

    except FileNotFoundError as e:
        logger.log_error(str(e), context="Orchestrator config not found")
        raise SystemExit(1)

    # Load environment
    logger.log("Loading environment variables")
    from cli.utils import load_env, validate_env_vars

    env = load_env(project)

    # Validate required vars
    required = ["GCP_PROJECT_ID", "GCP_REGION", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        logger.log_error(
            "Missing required environment variables", context=", ".join(required)
        )
        raise SystemExit(1)

    logger.success("Environment loaded")

    # Terraform
    if not skip_terraform:
        logger.step("Provisioning VMs with Terraform")

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
        logger.log("Running terraform init")
        returncode, stdout, stderr = run_with_progress(
            logger,
            "cd shared/terraform && terraform init -upgrade -migrate-state -input=false -no-color",
            "Initializing Terraform",
            cwd=project_root,
        )

        if returncode != 0:
            logger.log_error("Terraform init failed", context=stderr)
            raise SystemExit(1)

        # Generate tfvars
        logger.log("Generating terraform variables")
        tfvars_file = generate_tfvars(project_config_obj, preserve_ip=preserve_ip)
        logger.log(f"Terraform vars saved to: {tfvars_file}")

        # Select or create workspace using terraform_utils
        logger.log(f"Setting up terraform workspace: {project}")

        from cli.terraform_utils import select_workspace

        try:
            select_workspace(project, create=True)
            logger.success("Workspace ready")
        except Exception as e:
            logger.log_error("Workspace setup failed", context=str(e))
            raise SystemExit(1)

        # Refresh state
        logger.log("Refreshing terraform state")
        try:
            terraform_refresh(project, project_config_obj)
        except Exception:
            logger.log("State refresh failed (may be empty), continuing...")

        # Apply
        logger.log("Running terraform apply")
        apply_cmd = f"cd shared/terraform && terraform apply -auto-approve -no-color -compact-warnings -var-file={tfvars_file.name}"

        if preserve_ip:
            logger.log("Preserve IP mode enabled")

        returncode, stdout, stderr = run_with_progress(
            logger,
            apply_cmd,
            "Provisioning infrastructure (this may take 3-5 minutes)",
            cwd=project_root,
        )

        if returncode != 0:
            logger.log_error("Terraform apply failed", context=stderr)
            raise SystemExit(1)

        logger.success("VMs provisioned successfully")

        # Get VM IPs
        logger.step("Extracting VM IPs from terraform outputs")
        from cli.terraform_utils import get_terraform_outputs

        outputs = get_terraform_outputs(project)
        public_ips = outputs.get("vm_public_ips", {}).get("value", {})
        internal_ips = outputs.get("vm_internal_ips", {}).get("value", {})

        # Update .env with IPs
        logger.log("Updating .env with VM IPs")
        env_file = project_root / "projects" / project / ".env"

        if not env_file.exists():
            logger.log_error(f".env file not found: {env_file}")
            logger.log_error(
                "Run 'superdeploy generate -p {project}' first to create .env"
            )
            raise SystemExit(1)

        with open(env_file, "r") as f:
            env_lines = f.readlines()

        # Remove old IP lines and the comment header
        env_lines = [
            line
            for line in env_lines
            if not (
                line.startswith(
                    ("CORE_", "WEB_", "ALL_", "API_", "DASHBOARD_", "SERVICES_")
                )
                and "_IP=" in line
            )
            and "# VM IPs (Auto-populated by Terraform)" not in line
        ]

        # Remove trailing empty lines
        while env_lines and env_lines[-1].strip() == "":
            env_lines.pop()

        # Add new IPs with header (ensure single blank line before)
        if env_lines and not env_lines[-1].endswith("\n"):
            env_lines[-1] += "\n"
        env_lines.append("\n# VM IPs (Auto-populated by Terraform)\n")

        for vm_key, ip in sorted(public_ips.items()):
            env_key = vm_key.upper().replace("-", "_")
            env_lines.append(f"{env_key}_EXTERNAL_IP={ip}\n")

        for vm_key, ip in sorted(internal_ips.items()):
            env_key = vm_key.upper().replace("-", "_")
            env_lines.append(f"{env_key}_INTERNAL_IP={ip}\n")

        with open(env_file, "w") as f:
            f.writelines(env_lines)

        logger.success("VM IPs updated in .env")

        # Wait for VMs
        logger.step("Waiting for VMs to be ready")

        if public_ips:
            import time

            logger.log(f"Found {len(public_ips)} VMs to check")

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
                        subprocess.run(["ssh-keygen", "-R", vm_ip], capture_output=True)
                        break

                    if attempt < max_attempts:
                        time.sleep(10)

                if not vm_ready:
                    logger.warning(f"{vm_name} may not be fully ready")
                    all_ready = False

            if all_ready:
                logger.success("All VMs are ready")
            else:
                logger.warning("Some VMs may not be fully ready, continuing...")
        else:
            logger.log("No VMs found in outputs")

    else:
        logger.step("Skipping Terraform (--skip-terraform)")

    # Ansible
    if not skip_ansible:
        logger.step("Configuring services with Ansible")

        # Reload env (IPs may have changed)
        env = load_env(project)

        # Generate inventory
        logger.log("Generating Ansible inventory")
        from cli.commands.up import generate_ansible_inventory

        ansible_dir = project_root / "shared" / "ansible"
        generate_ansible_inventory(
            env, ansible_dir, project, orchestrator_ip, project_config_obj
        )
        logger.log("Inventory generated")

        # SSH known_hosts already cleaned during VM checks
        logger.log("SSH known_hosts cleaned")

        # Build ansible command
        from cli.ansible_utils import build_ansible_command

        ansible_vars = project_config_obj.to_ansible_vars()
        ansible_vars["forgejo_base_url"] = f"http://{orchestrator_ip}:3001"
        ansible_vars["orchestrator_ip"] = orchestrator_ip

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
            logger.log(f"Deploying only addon(s): {', '.join(enabled_addons_list)}")
        elif tags:
            ansible_tags = tags
        else:
            ansible_tags = "foundation,addons,project"

        logger.log(f"Running ansible with tags: {ansible_tags}")

        ansible_cmd = build_ansible_command(
            ansible_dir=ansible_dir,
            project_root=project_root,
            project_config=ansible_vars,
            env_vars=ansible_env_vars,
            tags=ansible_tags,
            project_name=project,
            ask_become_pass=False,
            enabled_addons=enabled_addons_list,
        )

        # Run ansible with clean tree view (or raw output if verbose)
        from cli.ansible_runner import AnsibleRunner

        runner = AnsibleRunner(logger, title="Configuring Services", verbose=verbose)
        result_returncode = runner.run(ansible_cmd, cwd=project_root)

        if result_returncode != 0:
            logger.log_error(
                "Ansible configuration failed", context="Check logs for details"
            )
            raise SystemExit(1)

        console.print("[green]✓ Services configured[/green]")
        logger.success("Services configured successfully")

    else:
        logger.step("Skipping Ansible (--skip-ansible)")

    # Sync secrets to Forgejo
    if not skip_sync and not skip_ansible:
        logger.step("Syncing secrets to Forgejo")
        try:
            from cli.commands.sync import sync

            # Call sync command programmatically
            from click.testing import CliRunner

            runner = CliRunner()
            result = runner.invoke(sync, ["-p", project, "--skip-github"])

            if result.exit_code == 0:
                logger.success("Secrets synced successfully")
            else:
                logger.warning(f"Secret sync had issues: {result.output}")
        except Exception as e:
            logger.log_error(f"Failed to sync secrets: {e}")
            logger.warning("Continuing deployment without secret sync")
    else:
        logger.step("Skipping secret sync (--skip-sync)")

    # Git push
    if not skip_git_push:
        logger.step("Pushing code to Git")
        logger.log("Git push not yet implemented in V2")
        logger.warning("Skipping git push (use --skip-git-push to suppress this)")

    # Display deployment summary
    console.print("\n" + "━" * 60)
    console.print("[bold green]✅ Infrastructure Deployed![/bold green]")
    console.print("━" * 60)

    # Load environment for IPs and credentials
    env = load_env(project)

    # Orchestrator info
    orchestrator_ip = env.get("ORCHESTRATOR_IP")
    if orchestrator_ip:
        console.print("\n[bold cyan]🎯 Orchestrator[/bold cyan]")
        console.print(f"  [dim]IP:[/dim] {orchestrator_ip}")
        console.print(f"  [dim]Forgejo:[/dim] http://{orchestrator_ip}:3001")

        # Get Forgejo credentials from orchestrator config
        project_root = get_project_root()
        orch_env_file = project_root / "shared" / "orchestrator" / ".env"
        if orch_env_file.exists():
            from dotenv import dotenv_values

            orch_env = dotenv_values(orch_env_file)
            forgejo_admin = orch_env.get("FORGEJO_ADMIN_USER", "admin")
            forgejo_pass = orch_env.get("FORGEJO_ADMIN_PASSWORD", "")
            grafana_pass = orch_env.get("GRAFANA_ADMIN_PASSWORD", "")

            console.print(f"  [dim]Forgejo:[/dim] http://{orchestrator_ip}:3001")
            if forgejo_pass:
                console.print(f"    Username: [bold]{forgejo_admin}[/bold]")
                console.print(f"    Password: [bold]{forgejo_pass}[/bold]")

            console.print(f"  [dim]Grafana:[/dim] http://{orchestrator_ip}:3000")
            if grafana_pass:
                console.print("    Username: [bold]admin[/bold]")
                console.print(f"    Password: [bold]{grafana_pass}[/bold]")

            console.print(f"  [dim]Prometheus:[/dim] http://{orchestrator_ip}:9090")

    # Project VMs and Apps
    console.print(f"\n[bold cyan]📦 Project: {project}[/bold cyan]")

    # Get VM IPs
    vm_ips = {}
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP"):
            vm_name = key.replace("_EXTERNAL_IP", "").lower().replace("_", "-")
            vm_ips[vm_name] = value

    if vm_ips:
        console.print("  [dim]VMs:[/dim]")
        for vm_name, ip in sorted(vm_ips.items()):
            console.print(f"    • {vm_name}: {ip}")

    # Display project credentials (postgres, rabbitmq, etc.)
    console.print("\n[bold cyan]🔐 Project Credentials:[/bold cyan]")

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
        console.print("\n  [cyan]🐘 PostgreSQL:[/cyan]")
        console.print(f"    Host: [bold]{postgres_host}[/bold]")
        console.print(f"    Database: [bold]{postgres_db}[/bold]")
        console.print(f"    Username: [bold]{postgres_user}[/bold]")
        console.print(f"    Password: [bold]{postgres_pass}[/bold]")

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
        console.print("\n  [cyan]🐰 RabbitMQ:[/cyan]")
        console.print(f"    Host: [bold]{rabbitmq_host}[/bold]")
        console.print(f"    Username: [bold]{rabbitmq_user}[/bold]")
        console.print(f"    Password: [bold]{rabbitmq_pass}[/bold]")
        if core_vm_ip:
            console.print(f"    Management UI: http://{core_vm_ip}:15672")

    # Redis (if exists)
    redis_host = env.get("REDIS_HOST", "")
    redis_pass = env.get("REDIS_PASSWORD", "")

    if redis_pass:
        console.print("\n  [cyan]📦 Redis:[/cyan]")
        console.print(f"    Host: [bold]{redis_host}[/bold]")
        console.print(f"    Password: [bold]{redis_pass}[/bold]")

    # Get app URLs
    apps = project_config_obj.raw_config.get("apps", {})
    if apps:
        console.print("\n  [dim]Applications:[/dim]")
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
                    console.print(f"    • {app_name}: https://{domain}")
                else:
                    console.print(f"    • {app_name}: http://{vm_ip}:{port}")


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

    # Get VM services from project config
    vm_services_map = {}
    if project_config:
        vms_config = project_config.raw_config.get("vms", {})
        for vm_role, vm_def in vms_config.items():
            services = list(vm_def.get("services", []))  # Make a copy

            # Always add caddy to every VM (for domain management and reverse proxy)
            if "caddy" not in services:
                services.append("caddy")

            vm_services_map[vm_role] = services

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
            # Convert to JSON and properly quote for INI format
            # INI parser needs quotes around JSON arrays
            services_json = json.dumps(services).replace('"', '\\"')

            inventory_lines.append(
                f'{vm["name"]} ansible_host={vm["host"]} ansible_user={vm["user"]} vm_role={role} vm_services="{services_json}"'
            )
        inventory_lines.append("")  # Empty line between groups

    inventory_content = "\n".join(inventory_lines)

    inventory_path = ansible_dir / "inventories" / f"{project_name}.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)
