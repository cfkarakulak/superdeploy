"""SuperDeploy CLI - Up command V2 (with improved logging and UX)"""

import click
import subprocess
import time
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
@click.option("--start-at-task", help="Resume Ansible from a specific task")
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
    start_at_task,
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
                logger, project_root, project, skip_terraform, skip_ansible,
                skip_git_push, skip_sync, skip, addon, tags, start_at_task,
                preserve_ip, verbose
            )
            
            if not verbose:
                console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
                console.print("[bold green]✅ Infrastructure Deployed![/bold green]")
                console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]\n")
                
        except Exception as e:
            logger.log_error(str(e), context=f"Project {project} deployment failed")
            raise SystemExit(1)


def _deploy_project_v2(
    logger, project_root, project, skip_terraform, skip_ansible,
    skip_git_push, skip_sync, skip, addon, tags, start_at_task,
    preserve_ip, verbose
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
                context="Deploy it first: superdeploy orchestrator up"
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
        logger.log_error("Missing required environment variables", context=", ".join(required))
        raise SystemExit(1)
    
    logger.success("Environment loaded")
    
    # Terraform
    if not skip_terraform:
        logger.step("Provisioning VMs with Terraform")
        
        from cli.terraform_utils import (
            terraform_init,
            terraform_apply,
            select_workspace,
            terraform_refresh,
            generate_tfvars,
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
        tfvars_file = generate_tfvars(project_config_obj, preserve_ip=preserve_ip)
        logger.log(f"Terraform vars saved to: {tfvars_file}")
        
        # Select workspace
        logger.log(f"Selecting terraform workspace: {project}")
        returncode, stdout, stderr = run_with_progress(
            logger,
            f"cd shared/terraform && terraform workspace select {project} || terraform workspace new {project}",
            "Selecting workspace",
            cwd=project_root
        )
        
        if returncode != 0:
            logger.log_error("Workspace selection failed", context=stderr)
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
            cwd=project_root
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
            logger.log_error("Run 'superdeploy generate -p {project}' first to create .env")
            raise SystemExit(1)
        
        with open(env_file, 'r') as f:
            env_lines = f.readlines()
        
        # Remove old IP lines
        env_lines = [line for line in env_lines if not line.startswith(('CORE_', 'WEB_', 'ALL_')) or '_IP=' not in line]
        
        # Add new IPs
        env_lines.append("\n# VM IPs (Auto-populated by Terraform)\n")
        for vm_key, ip in sorted(public_ips.items()):
            env_key = vm_key.upper().replace('-', '_')
            env_lines.append(f"{env_key}_EXTERNAL_IP={ip}\n")
        
        for vm_key, ip in sorted(internal_ips.items()):
            env_key = vm_key.upper().replace('-', '_')
            env_lines.append(f"{env_key}_INTERNAL_IP={ip}\n")
        
        with open(env_file, 'w') as f:
            f.writelines(env_lines)
        
        logger.success("VM IPs updated in .env")
        
        # Wait for VMs
        logger.step("Waiting for VMs to be ready")
        
        if public_ips:
            import subprocess
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
                    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)
                    
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
        generate_ansible_inventory(env, ansible_dir, project, orchestrator_ip, project_config_obj)
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
        
        ansible_tags = tags if tags else "foundation,addons,project"
        
        logger.log(f"Running ansible with tags: {ansible_tags}")
        if start_at_task:
            logger.log(f"Resuming from task: {start_at_task}")
        
        ansible_cmd = build_ansible_command(
            ansible_dir=ansible_dir,
            project_root=project_root,
            project_config=ansible_vars,
            env_vars=ansible_env_vars,
            tags=ansible_tags,
            project_name=project,
            ask_become_pass=False,
            start_at_task=start_at_task,
        )
        
        logger.log_command(ansible_cmd)
        
        # Run ansible with real-time output streaming and task tracking
        import subprocess
        import re
        import time
        from rich.tree import Tree
        from rich.live import Live
        from rich.text import Text
        
        # Create progress tree
        progress_tree = Tree("🔧 [cyan]Configuring Services[/cyan]")
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
            logger.log_error("Ansible configuration failed")
            raise SystemExit(1)
        
        console.print("[green]✓ Services configured[/green]")
        
        logger.success("Services configured successfully")
    
    else:
        logger.step("Skipping Ansible (--skip-ansible)")
    
    # Git push
    if not skip_git_push:
        logger.step("Pushing code to Git")
        logger.log("Git push not yet implemented in V2")
        logger.warning("Skipping git push (use --skip-git-push to suppress this)")
    
    # Display info
    if not verbose and not skip_terraform:
        from cli.terraform_utils import get_terraform_outputs
        
        outputs = get_terraform_outputs(project)
        public_ips = outputs.get("vm_public_ips", {}).get("value", {})
        
        if public_ips:
            console.print(f"\n[cyan]📍 VM IPs:[/cyan]")
            for vm_key, ip in sorted(public_ips.items()):
                console.print(f"  {vm_key}: {ip}")



def generate_ansible_inventory(env, ansible_dir, project_name, orchestrator_ip=None, project_config=None):
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
        inventory_lines.append(f"orchestrator-main-0 ansible_host={orchestrator_ip} ansible_user=superdeploy vm_role=orchestrator")
        inventory_lines.append("")

    # Add project VM groups
    for role in sorted(vm_groups.keys()):
        inventory_lines.append(f"[{role}]")
        for vm in sorted(vm_groups[role], key=lambda x: x["name"]):
            # Get services for this VM role
            services = vm_services_map.get(role, [])
            services_json = json.dumps(services).replace('"', '\\"')
            
            inventory_lines.append(
                f"{vm['name']} ansible_host={vm['host']} ansible_user={vm['user']} vm_role={role} vm_services='{services_json}'"
            )
        inventory_lines.append("")  # Empty line between groups

    inventory_content = "\n".join(inventory_lines)

    inventory_path = ansible_dir / "inventories" / f"{project_name}.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)
