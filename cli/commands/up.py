"""SuperDeploy CLI - Up command (Deploy infrastructure)"""

import click
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from cli.utils import (
    load_env,
    run_command,
    get_project_root,
    validate_env_vars,
)
from cli.ansible_utils import build_ansible_command
from cli.terraform_utils import (
    get_terraform_dir,
    select_workspace,
    generate_tfvars,
    terraform_init,
    terraform_apply,
    terraform_refresh,
)

console = Console()


def filter_addons(enabled_addons, skip_addons, only_addons, project):
    """
    Filter addon list based on --skip and --addon flags

    Args:
        enabled_addons: List of all enabled addons
        skip_addons: Tuple of addon names to skip
        only_addons: String of comma-separated addon names to deploy (or None)
        project: Project name for error messages

    Returns:
        Filtered list of addons to deploy
    """
    if not enabled_addons:
        return []

    # If --addon specified, only deploy those
    if only_addons:
        requested = [a.strip() for a in only_addons.split(',')]
        filtered = []
        for addon in requested:
            if addon in enabled_addons:
                filtered.append(addon)
            else:
                console.print(
                    f"[yellow]⚠️  Warning: Addon '{addon}' not found in project (ignoring)[/yellow]"
                )
        
        if filtered:
            console.print(f"[cyan]📦 Deploying only: {', '.join(filtered)}[/cyan]")
        return filtered

    # Otherwise, start with all enabled addons
    filtered = list(enabled_addons)

    # Apply --skip filter
    if skip_addons:
        skipped = []
        for addon in skip_addons:
            if addon in filtered:
                filtered.remove(addon)
                skipped.append(addon)
            elif addon not in enabled_addons:
                console.print(
                    f"[yellow]⚠️  Warning: Addon '{addon}' not found in project (ignoring)[/yellow]"
                )

        if skipped:
            console.print(f"[yellow]⚠️  Skipping addons: {', '.join(skipped)}[/yellow]")

    return filtered


def display_deployment_plan(all_addons, filtered_addons, skip_addons):
    """Display deployment plan showing which addons will be deployed"""
    if not all_addons:
        return

    console.print("\n[bold cyan]📋 Deployment Plan[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    for addon in all_addons:
        if addon in filtered_addons:
            console.print(f"  [green]✓[/green] {addon}")
        else:
            if skip_addons and addon in skip_addons:
                console.print(f"  [dim]○ {addon} [dim](skipped)[/dim][/dim]")

    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print(
        f"[cyan]Total: {len(filtered_addons)}/{len(all_addons)} addons will be deployed[/cyan]\n"
    )


def check_prerequisites():
    """Check if required tools are installed"""
    required_tools = {
        "terraform": "brew install terraform",
        "ansible": "brew install ansible",
        "gcloud": "brew install google-cloud-sdk",
        "jq": "brew install jq",
        "gh": "brew install gh",
    }

    missing = []
    for tool, install_cmd in required_tools.items():
        try:
            subprocess.run(["which", tool], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            missing.append((tool, install_cmd))

    if missing:
        console.print("[red]❌ Missing required tools:[/red]")
        for tool, cmd in missing:
            console.print(f"  • {tool}: [cyan]{cmd}[/cyan]")
        return False

    return True


def update_ips_in_env(project_root, project_name):
    """Extract VM IPs from Terraform and update project's .env (dynamic for any VM configuration)"""
    console.print("[cyan]📍 Extracting VM IPs...[/cyan]")

    env_file_path = project_root / "projects" / project_name / ".env"

    # Get all VM IPs from Terraform dynamically using terraform_utils
    try:
        from cli.terraform_utils import get_terraform_outputs

        # This automatically selects the correct workspace
        outputs = get_terraform_outputs(project_name)

        public_ips = outputs.get("vm_public_ips", {}).get("value", {})
        internal_ips = outputs.get("vm_internal_ips", {}).get("value", {})

        # Build environment variables dynamically
        # Format: {vm-role}-{index}_EXTERNAL_IP and {vm-role}-{index}_INTERNAL_IP
        ip_vars = {}

        for vm_key in public_ips.keys():
            # Convert vm-key to ENV_VAR format (e.g., "core-0" -> "CORE_0")
            env_prefix = vm_key.upper().replace("-", "_")
            ip_vars[f"{env_prefix}_EXTERNAL_IP"] = public_ips[vm_key]
            ip_vars[f"{env_prefix}_INTERNAL_IP"] = internal_ips[vm_key]

        # Read existing .env
        if env_file_path.exists():
            with open(env_file_path, "r") as f:
                lines = f.readlines()
        else:
            lines = []

        # Update existing or append new
        updated_vars = set()
        new_lines = []

        for line in lines:
            updated = False
            for var_name, var_value in ip_vars.items():
                if line.startswith(f"{var_name}="):
                    new_lines.append(f"{var_name}={var_value}\n")
                    updated_vars.add(var_name)
                    updated = True
                    break
            if not updated:
                new_lines.append(line)

        # Append missing vars
        if updated_vars != set(ip_vars.keys()):
            new_lines.append("\n# VM IPs (Auto-populated by Terraform)\n")
            for var_name, var_value in ip_vars.items():
                if var_name not in updated_vars:
                    new_lines.append(f"{var_name}={var_value}\n")

        # Write back
        with open(env_file_path, "w") as f:
            f.writelines(new_lines)

        console.print("[green]✅ Updated IPs:[/green]")
        for vm_key in sorted(public_ips.keys()):
            console.print(f"  {vm_key}: {public_ips[vm_key]} ({internal_ips[vm_key]})")

        return True
    except Exception as e:
        console.print(f"[red]❌ Failed to extract IPs: {e}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


def generate_ansible_inventory(env, ansible_dir, project_name, orchestrator_ip=None, project_config=None):
    """Generate Ansible inventory file dynamically from environment variables

    Args:
        env: Environment variables dict
        ansible_dir: Path to ansible directory
        project_name: Project name
        orchestrator_ip: Orchestrator VM IP (from global config)
        project_config: Project configuration object (to get VM services)
    """
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
            # Add caddy to VMs that have apps
            apps = project_config.raw_config.get("apps", {})
            for app_name, app_config in apps.items():
                if app_config.get("vm") == vm_role:
                    if "caddy" not in services:
                        services.append("caddy")
                    break
            vm_services_map[vm_role] = services

    # Build inventory content
    inventory_lines = []

    # NOTE: Orchestrator is NOT included in project inventory
    # It has its own deployment via 'superdeploy orchestrator up'
    # and should not receive project-specific addons

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

    console.print(
        f"[green]✅ Ansible inventory generated: {inventory_path.name}[/green]"
    )

    if orchestrator_ip:
        console.print(f"[cyan]   Orchestrator: {orchestrator_ip}[/cyan]")


def check_single_vm_ssh(vm_key, ip, ssh_key, ssh_user):
    """Check if a single VM is SSH-ready with sudo access"""
    try:
        result = subprocess.run(
            f"ssh -i {ssh_key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_user}@{ip} 'sudo -n whoami' 2>&1",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and "root" in result.stdout:
            return (vm_key, ip, True, None)
        else:
            return (vm_key, ip, False, result.stdout.strip()[:50])
    except Exception as e:
        return (vm_key, ip, False, str(e))


def check_vms_parallel(public_ips, ssh_key, ssh_user, max_attempts=18, delay=10):
    """Check all VMs in parallel until all are ready or timeout"""
    all_ready = False
    attempt = 0

    while attempt < max_attempts and not all_ready:
        attempt += 1
        console.print(f"  [dim]Attempt {attempt}/{max_attempts}...[/dim]")

        ready_vms = {}

        # Check all VMs concurrently
        with ThreadPoolExecutor(max_workers=len(public_ips)) as executor:
            futures = {
                executor.submit(
                    check_single_vm_ssh, vm_key, ip, ssh_key, ssh_user
                ): vm_key
                for vm_key, ip in public_ips.items()
            }

            for future in as_completed(futures):
                vm_key, ip, is_ready, error = future.result()
                ready_vms[vm_key] = is_ready

                if is_ready:
                    console.print(f"    [green]✓[/green] {vm_key} ({ip}) ready")
                else:
                    console.print(
                        f"    [yellow]⏳[/yellow] {vm_key} ({ip}) not ready yet"
                    )

        if all(ready_vms.values()):
            all_ready = True
            console.print("[green]✅ All VMs ready![/green]")
        else:
            if attempt < max_attempts:
                console.print("  [dim]Waiting 10s before next check...[/dim]")
                time.sleep(delay)

    return all_ready


def clean_ssh_known_hosts(env):
    """Clean SSH known_hosts to avoid conflicts (dynamic for all VMs)"""
    console.print("[cyan]🔐 Cleaning SSH known_hosts...[/cyan]")

    # Clean all VM IPs from known_hosts
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP") and value:
            subprocess.run(["ssh-keygen", "-R", value], capture_output=True)

    console.print("[green]✅ SSH known_hosts cleaned[/green]")


def push_to_github(project_root, github_token, github_org, github_repo):
    """Push to GitHub"""
    try:
        subprocess.run(
            ["git", "remote", "remove", "github"],
            capture_output=True,
            cwd=str(project_root),
        )
    except:
        pass

    try:
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "github",
                f"https://{github_token}@github.com/{github_org}/{github_repo}.git",
            ],
            check=False,
            capture_output=True,
            cwd=str(project_root),
        )
    except:
        pass

    result = subprocess.run(
        ["git", "push", "-u", "github", "master"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return (
        "github",
        result.returncode == 0,
        result.stderr if result.returncode != 0 else None,
    )


def push_to_forgejo(project_root, forgejo_url):
    """Push to Forgejo"""
    subprocess.run(
        ["git", "remote", "remove", "forgejo"],
        capture_output=True,
        cwd=str(project_root),
    )

    result = subprocess.run(
        ["git", "remote", "add", "forgejo", forgejo_url],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )

    if result.returncode != 0:
        return ("forgejo", False, result.stderr)

    result = subprocess.run(
        ["git", "push", "forgejo", "master:master", "-f"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return (
        "forgejo",
        result.returncode == 0,
        result.stderr if result.returncode != 0 else None,
    )


def push_git_parallel(project_root, github_token, github_org, github_repo, forgejo_url):
    """Push to GitHub and Forgejo in parallel"""
    results = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []

        if github_token and github_org and github_repo:
            futures.append(
                executor.submit(
                    push_to_github, project_root, github_token, github_org, github_repo
                )
            )

        if forgejo_url:
            futures.append(executor.submit(push_to_forgejo, project_root, forgejo_url))

        for future in as_completed(futures):
            remote, success, error = future.result()
            results[remote] = (success, error)

    return results


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-git-push", is_flag=True, help="Skip Git push")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
@click.option("--addon", help="Deploy only specific addon(s), comma-separated (e.g. --addon caddy,postgres). Automatically sets --tags to addons.")
@click.option(
    "--tags",
    help="Run only specific Ansible tags (e.g. 'addons', 'project', 'foundation,addons')",
)
@click.option(
    "--start-at-task",
    help="Resume Ansible from a specific task. Use partial match (e.g. 'caddy', 'Docker'). Saves time when rerunning after failures.",
)
@click.option(
    "--preserve-ip",
    is_flag=True,
    help="Preserve existing static IPs (prevents IP changes on redeploy)",
)
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
):
    """
    Deploy infrastructure (like 'heroku create')

    This command will:
    - Provision VMs with Terraform
    - Configure services with Ansible
    - Push code to Forgejo
    - Setup Forgejo runner

    \b
    Estimated time: ~10 minutes
    """
    console.print(
        Panel.fit(
            "[bold cyan]🚀 SuperDeploy Infrastructure Deployment[/bold cyan]\n\n"
            "[white]Deploying shared infrastructure (Terraform + Ansible)...[/white]",
            border_style="cyan",
        )
    )

    # Check prerequisites
    if not check_prerequisites():
        raise SystemExit(1)

    project_root = get_project_root()

    # Load project config using ConfigLoader
    from cli.core.config_loader import ConfigLoader
    from cli.core.orchestrator_loader import OrchestratorLoader

    projects_dir = project_root / "projects"
    shared_dir = project_root / "shared"
    config_loader = ConfigLoader(projects_dir)
    orchestrator_loader = OrchestratorLoader(shared_dir)

    try:
        project_config_obj = config_loader.load_project(project)
        console.print("[dim]✓ Loaded project config[/dim]")
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        raise SystemExit(1)

    # Load orchestrator config
    orchestrator_ip = None
    try:
        orchestrator_config = orchestrator_loader.load()
        console.print("[dim]✓ Loaded orchestrator config[/dim]")

        # Check if orchestrator needs to be deployed
        if orchestrator_config.should_deploy():
            console.print(
                "[yellow]⚠️  Orchestrator not deployed yet. Deploy it first:[/yellow]"
            )
            console.print("[yellow]   superdeploy orchestrator up[/yellow]")
            console.print(
                "[yellow]   Or set deployment_mode: 'skip' in shared/orchestrator.yml if using existing[/yellow]"
            )
            raise SystemExit(1)

        orchestrator_ip = orchestrator_config.get_ip()
        if not orchestrator_ip:
            console.print(
                "[yellow]⚠️  Orchestrator IP not found. Please deploy orchestrator first.[/yellow]"
            )
            raise SystemExit(1)

        console.print(f"[dim]✓ Using orchestrator: {orchestrator_ip}[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    env = load_env(project)

    # Validate required vars
    required = ["GCP_PROJECT_ID", "GCP_REGION", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    # Forgejo is always managed by orchestrator (not by projects)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        # Terraform
        if not skip_terraform:
            task1 = progress.add_task("[cyan]Provisioning VMs (Terraform)...", total=3)

            # Init
            terraform_dir = get_terraform_dir()
            terraform_init()
            progress.advance(task1)

            # Generate tfvars from project config
            tfvars_file = generate_tfvars(project_config_obj, preserve_ip=preserve_ip)

            # Select workspace (creates if doesn't exist)
            select_workspace(project, create=True)

            # Refresh state to sync with actual infrastructure
            try:
                terraform_refresh(project, project_config_obj)
            except Exception:
                # Refresh may fail if state is empty, that's ok
                pass

            # Apply
            terraform_apply(
                project, project_config_obj, var_file=tfvars_file, auto_approve=True, preserve_ip=preserve_ip
            )
            progress.advance(task1)
            progress.advance(task1)

            console.print("[green]✅ VMs provisioned![/green]")

            # Wait for VMs to boot and be SSH-ready
            console.print("[yellow]⏳ Waiting for VMs to be SSH-ready...[/yellow]")

            # Get VM IPs first
            from cli.terraform_utils import get_terraform_outputs

            outputs = get_terraform_outputs(project)
            public_ips = outputs.get("vm_public_ips", {}).get("value", {})

            if not public_ips:
                console.print(
                    "[yellow]⚠️  No VMs found in outputs, skipping health check[/yellow]"
                )
            else:
                # Check all VMs in parallel
                ssh_key = env.get("SSH_KEY_PATH")
                ssh_user = env.get("SSH_USER")
                all_ready = check_vms_parallel(public_ips, ssh_key, ssh_user)

                if not all_ready:
                    console.print(
                        "[yellow]⚠️  Some VMs may not be fully ready, continuing anyway...[/yellow]"
                    )

    # Update IPs from Terraform (even if skipped, read current state)
    update_ips_in_env(project_root, project)

    # Reload env (in case IPs changed from Terraform)
    env = load_env(project)

    # Generate inventory with NEW IPs
    ansible_dir = project_root / "shared" / "ansible"
    generate_ansible_inventory(env, ansible_dir, project, orchestrator_ip, project_config_obj)

    # Clean SSH known_hosts with NEW IPs
    clean_ssh_known_hosts(env)

    # Ansible (outside progress context to avoid output mixing)
    if not skip_ansible:
        console.print("\n[cyan]⚙️  Configuring services (Ansible)...[/cyan]")

        ansible_dir = project_root / "shared" / "ansible"

        # Prepare environment variables for Ansible
        # Build ansible_env_vars dynamically from all env vars
        ansible_env_vars = {
            "superdeploy_root": str(project_root),
        }

        # Add all VM IPs to ansible env vars dynamically (both formats)
        for key, value in env.items():
            if key.endswith("_EXTERNAL_IP") or key.endswith("_INTERNAL_IP"):
                # Add both uppercase and lowercase for compatibility
                ansible_env_vars[key] = value  # CORE_0_EXTERNAL_IP
                ansible_env_vars[key.lower()] = value  # core_0_external_ip

        # Get Ansible vars from ConfigLoader (includes enabled_addons, addon_configs, etc.)
        ansible_vars = project_config_obj.to_ansible_vars()
        
        # Add orchestrator info for forgejo runner setup
        if orchestrator_ip:
            ansible_vars["forgejo_base_url"] = f"http://{orchestrator_ip}:3001"
            ansible_vars["orchestrator_ip"] = orchestrator_ip

        # Filter addons based on --skip and --addon flags
        enabled_addons = ansible_vars.get("enabled_addons", [])
        
        # If --addon specified, pass it to Ansible to filter per-VM
        if addon:
            # Parse comma-separated addons
            addon_list = [a.strip() for a in addon.split(',')]
            console.print(f"\n[yellow]📦 Deploying only: {', '.join(addon_list)}[/yellow]")
            console.print("[dim]Note: Each VM will only deploy addons in its services list[/dim]")
            # Pass addon filter to Ansible
            ansible_vars["addon_filter"] = addon_list
            # Auto-set tags to addons only
            if not tags:
                tags = "addons"
            filtered_addons = enabled_addons  # Don't filter here, let Ansible do it per-VM
        else:
            filtered_addons = filter_addons(enabled_addons, skip, addon, project)
            ansible_vars["addon_filter"] = []

        # Update ansible_vars with filtered addons (for display only)
        ansible_vars["enabled_addons"] = filtered_addons

        # Display deployment plan
        if addon:
            console.print(f"\n[cyan]📋 Will deploy to VMs based on their services configuration[/cyan]")
        else:
            display_deployment_plan(enabled_addons, filtered_addons, skip)

        # Display resume point if provided
        if start_at_task:
            console.print(
                f"\n[yellow]⏩ Resuming from task: '{start_at_task}'[/yellow]"
            )
            console.print("[dim]Skipping all tasks before this point[/dim]\n")

        # Build Ansible command using shared utility
        # Use custom tags if provided, otherwise run all phases
        ansible_tags = tags if tags else "foundation,addons,project"

        ansible_cmd = build_ansible_command(
            ansible_dir=ansible_dir,
            project_root=project_root,
            project_config=ansible_vars,
            env_vars=ansible_env_vars,
            tags=ansible_tags,
            project_name=project,
            ask_become_pass=False,  # Passwordless sudo should be configured by foundation phase
            start_at_task=start_at_task,  # Resume from specific task if provided
        )

        # Run ansible with interactive input if asking for become password
        if skip_terraform:
            # Need interactive mode for password prompt
            result = subprocess.run(
                ansible_cmd,
                shell=True,
                cwd=str(project_root),
            )
            if result.returncode != 0:
                console.print("[red]❌ Ansible configuration failed![/red]")
                raise SystemExit(1)
        else:
            run_command(ansible_cmd)

        console.print("[green]✅ Services configured![/green]")

    # Git push (also outside progress to avoid mixing)
    if not skip_git_push:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task3 = progress.add_task("[cyan]Pushing code...", total=1)

            # Prepare git push parameters
            import urllib.parse

            # Reload env again in case IPs changed late
            env = load_env(project)

            github_token = env.get("GITHUB_TOKEN")

            # Get Forgejo host from orchestrator
            forgejo_host = orchestrator_ip
            forgejo_url = None

            if forgejo_host:
                # Get Forgejo port from orchestrator config
                from cli.core.orchestrator_loader import OrchestratorLoader

                orch_loader = OrchestratorLoader(project_root / "shared")
                orch_config = orch_loader.load()
                forgejo_config = orch_config.get_forgejo_config()
                forgejo_port = forgejo_config.get("port")
                if not forgejo_port:
                    console.print(
                        "[red]❌ forgejo.port not found in orchestrator config![/red]"
                    )
                    raise SystemExit(1)

                # Wait until Forgejo is reachable
                for _ in range(30):
                    try:
                        reachable = (
                            subprocess.run(
                                [
                                    "bash",
                                    "-lc",
                                    f"curl -sSf -m 3 http://{forgejo_host}:{forgejo_port}/ >/dev/null",
                                ],
                                capture_output=True,
                                cwd=str(project_root),
                            ).returncode
                            == 0
                        )
                        if reachable:
                            break
                    except Exception:
                        pass
                    time.sleep(5)

                # Load Forgejo credentials from orchestrator
                from dotenv import dotenv_values

                orchestrator_env = dotenv_values(
                    project_root / "shared" / "orchestrator" / ".env"
                )
                admin_password = orchestrator_env.get("FORGEJO_ADMIN_PASSWORD")

                admin_user = forgejo_config.get("admin_user")
                if not admin_user:
                    console.print(
                        "[red]❌ forgejo.admin_user not found in orchestrator config![/red]"
                    )
                    raise SystemExit(1)

                org = forgejo_config.get("org")
                if not org:
                    console.print(
                        "[red]❌ forgejo.org not found in orchestrator config![/red]"
                    )
                    raise SystemExit(1)

                repo_name = forgejo_config.get("repo")
                if not repo_name:
                    console.print(
                        "[red]❌ forgejo.repo not found in orchestrator config![/red]"
                    )
                    raise SystemExit(1)

                encoded_pass = urllib.parse.quote(admin_password)
                forgejo_url = (
                    f"http://{admin_user}:{encoded_pass}"
                    f"@{forgejo_host}:{forgejo_port}/{org}/{repo_name}.git"
                )

            # Push to both remotes in parallel
            github_org = env.get("GITHUB_ORG")
            github_repo = env.get("GITHUB_REPO")
            results = push_git_parallel(
                project_root, github_token, github_org, github_repo, forgejo_url
            )

            # Report results
            for remote, (success, error) in results.items():
                if success:
                    if remote == "github":
                        console.print(
                            "[green]✅ Superdeploy backed up to GitHub![/green]"
                        )
                    else:
                        console.print("[green]✅ Workflows pushed to Forgejo![/green]")
                else:
                    console.print(
                        f"[yellow]⚠️  {remote.capitalize()} push failed: {error}[/yellow]"
                    )

            progress.advance(task3)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Infrastructure Deployed![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")

    # Display Forgejo info (from orchestrator)
    if orchestrator_ip:
        from cli.core.orchestrator_loader import OrchestratorLoader

        orch_loader = OrchestratorLoader(project_root / "shared")
        orch_config = orch_loader.load()
        forgejo_config = orch_config.get_forgejo_config()
        forgejo_port = forgejo_config.get("port")
        if not forgejo_port:
            console.print(
                "[red]❌ forgejo.port not found in orchestrator config![/red]"
            )
            raise SystemExit(1)

        console.print(
            f"\n[cyan]🌐 Forgejo:[/cyan] http://{orchestrator_ip}:{forgejo_port}"
        )
        # Load credentials from orchestrator
        from dotenv import dotenv_values

        orchestrator_env = dotenv_values(
            project_root / "shared" / "orchestrator" / ".env"
        )
        admin_password = orchestrator_env.get("FORGEJO_ADMIN_PASSWORD")
        if not admin_password:
            console.print(
                "[red]❌ FORGEJO_ADMIN_PASSWORD not found in orchestrator .env![/red]"
            )
            raise SystemExit(1)

        admin_user = forgejo_config.get("admin_user")
        if not admin_user:
            console.print(
                "[red]❌ forgejo.admin_user not found in orchestrator config![/red]"
            )
            raise SystemExit(1)

        console.print(f"[cyan]👤 Login:[/cyan]   {admin_user} / {admin_password}")

    # Update orchestrator monitoring with new project targets
    if orchestrator_ip and not skip_terraform:
        console.print("\n[bold cyan]📊 Updating monitoring configuration...[/bold cyan]")
        try:
            from cli.monitoring_utils import update_orchestrator_monitoring
            
            # Get project IPs from env and map to services
            env = load_env(project)
            project_targets = []
            vm_services_map = {}
            
            # Get VMs config to map IPs to services
            vms_config = project_config_obj.get_vms()
            apps_config = project_config_obj.get_apps()
            
            for key, value in env.items():
                if key.endswith("_EXTERNAL_IP") and value:
                    # Parse VM key from env var (e.g., "API_0_EXTERNAL_IP" -> "api")
                    vm_key = key.replace("_EXTERNAL_IP", "").lower()
                    # Extract role (e.g., "api_0" -> "api")
                    vm_role = vm_key.rsplit("_", 1)[0]
                    
                    # Find service name from apps config
                    service_name = vm_role  # Default to VM role
                    for app_name, app_config in apps_config.items():
                        if app_config.get('vm') == vm_role:
                            service_name = app_name
                            break
                    
                    target = f"{value}:2019"
                    project_targets.append(target)
                    vm_services_map[target] = {
                        'service': service_name,
                        'vm': vm_role
                    }
            
            if project_targets:
                # Get SSH config from cloud config
                cloud_config = project_config_obj.raw_config.get("cloud", {})
                ssh_config = cloud_config.get("ssh", {})
                
                success = update_orchestrator_monitoring(
                    orchestrator_ip=orchestrator_ip,
                    project_name=project,
                    project_targets=project_targets,
                    ssh_key_path=ssh_config.get('key_path', '~/.ssh/superdeploy_deploy'),
                    ssh_user=ssh_config.get('user', 'superdeploy'),
                    vm_services_map=vm_services_map
                )
                
                if success:
                    console.print("[green]✅ Monitoring updated![/green]")
                else:
                    console.print("[yellow]⚠️  Monitoring update failed (non-critical)[/yellow]")
            else:
                console.print("[dim]No external IPs found, skipping monitoring update[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Monitoring update failed: {e}[/yellow]")
    
    # Auto-sync GitHub secrets (unless --skip-sync flag)
    if not skip_sync:
        console.print("\n[bold cyan]🔄 Syncing GitHub secrets...[/bold cyan]")

        # Run sync synchronously
        try:
            sync_cmd = [
                "superdeploy",
                "sync",
                "-p",
                project,
            ]

            result = subprocess.run(
                sync_cmd,
                cwd=str(project_root),
            )

            if result.returncode == 0:
                console.print("[green]✅ GitHub secrets synced![/green]")
            else:
                console.print(
                    "[yellow]⚠️  Sync had issues (check output above)[/yellow]"
                )
                console.print(
                    f"[dim]Or run manually: superdeploy sync -p {project}[/dim]"
                )

        except Exception as e:
            console.print(f"[yellow]⚠️  Sync failed: {e}[/yellow]")
            console.print(
                f"[dim]Run 'superdeploy sync -p {project}' manually to update GitHub secrets[/dim]"
            )
    else:
        console.print(
            f"\n[yellow]Note:[/yellow] Run [bold cyan]superdeploy sync -p {project}[/bold cyan] to configure GitHub secrets"
        )
