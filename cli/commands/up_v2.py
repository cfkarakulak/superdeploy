"""SuperDeploy CLI - Up command V2 (with improved logging and UX)"""

import click
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
            "cd shared/terraform && terraform init -upgrade",
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
        apply_cmd = f"cd shared/terraform && terraform apply -auto-approve -var-file={tfvars_file.name}"
        
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
        
        # Update IPs
        logger.log("Extracting VM IPs from terraform outputs")
        from cli.commands.up import update_ips_in_env
        
        if not update_ips_in_env(project_root, project):
            logger.warning("Failed to update IPs, continuing...")
        else:
            logger.success("VM IPs updated in .env")
        
        # Wait for VMs
        logger.step("Waiting for VMs to be ready")
        from cli.terraform_utils import get_terraform_outputs
        
        outputs = get_terraform_outputs(project)
        public_ips = outputs.get("vm_public_ips", {}).get("value", {})
        
        if public_ips:
            logger.log(f"Found {len(public_ips)} VMs to check")
            from cli.commands.up import check_vms_parallel
            
            ssh_key = env.get("SSH_KEY_PATH")
            ssh_user = env.get("SSH_USER")
            
            all_ready = check_vms_parallel(public_ips, ssh_key, ssh_user)
            
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
        
        # Clean SSH known_hosts
        logger.log("Cleaning SSH known_hosts")
        from cli.commands.up import clean_ssh_known_hosts
        clean_ssh_known_hosts(env)
        
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
        
        # Run ansible
        import subprocess
        if verbose:
            result = subprocess.run(ansible_cmd, shell=True, cwd=str(project_root))
            if result.returncode != 0:
                logger.log_error("Ansible configuration failed")
                raise SystemExit(1)
        else:
            from rich.live import Live
            from rich.spinner import Spinner
            
            with Live(
                Spinner("dots", text="[cyan]Configuring services (this may take 10-15 minutes)...[/cyan]"),
                console=console,
                refresh_per_second=10,
            ) as live:
                result = subprocess.run(
                    ansible_cmd,
                    shell=True,
                    cwd=str(project_root),
                    capture_output=True,
                    text=True
                )
                
                logger.log_output(result.stdout, "stdout")
                logger.log_output(result.stderr, "stderr")
                
                if result.returncode == 0:
                    live.update("[green]✓ Services configured[/green]")
                else:
                    live.update("[red]✗ Configuration failed[/red]")
            
            if result.returncode != 0:
                logger.log_error("Ansible configuration failed", context="Check logs for details")
                raise SystemExit(1)
        
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
