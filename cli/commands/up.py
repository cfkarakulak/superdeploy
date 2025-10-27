"""SuperDeploy CLI - Up command (Deploy infrastructure)"""

import click
import subprocess
import time
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


def filter_addons(enabled_addons, skip_addons, project):
    """
    Filter addon list based on --skip flags

    Args:
        enabled_addons: List of all enabled addons
        skip_addons: Tuple of addon names to skip
        project: Project name for error messages

    Returns:
        Filtered list of addons to deploy
    """
    if not enabled_addons:
        return []

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


def generate_ansible_inventory(env, ansible_dir, project_name):
    """Generate Ansible inventory file dynamically from environment variables"""
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

            vm_groups[role].append(
                {
                    "name": f"{project_name}-{vm_key}",
                    "host": value,
                    "user": env.get("SSH_USER", "superdeploy"),
                }
            )

    # Build inventory content
    inventory_lines = []
    for role in sorted(vm_groups.keys()):
        inventory_lines.append(f"[{role}]")
        for vm in sorted(vm_groups[role], key=lambda x: x["name"]):
            inventory_lines.append(
                f"{vm['name']} ansible_host={vm['host']} ansible_user={vm['user']}"
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


def clean_ssh_known_hosts(env):
    """Clean SSH known_hosts to avoid conflicts (dynamic for all VMs)"""
    console.print("[cyan]🔐 Cleaning SSH known_hosts...[/cyan]")

    # Clean all VM IPs from known_hosts
    for key, value in env.items():
        if key.endswith("_EXTERNAL_IP") and value:
            subprocess.run(["ssh-keygen", "-R", value], capture_output=True)

    console.print("[green]✅ SSH known_hosts cleaned[/green]")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-git-push", is_flag=True, help="Skip Git push")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
@click.option(
    "--tags",
    help="Run only specific Ansible tags (e.g. 'addons', 'project', 'foundation,addons')",
)
def up(project, skip_terraform, skip_ansible, skip_git_push, skip_sync, skip, tags):
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

    projects_dir = project_root / "projects"
    config_loader = ConfigLoader(projects_dir)

    try:
        project_config_obj = config_loader.load_project(project)
        console.print("[dim]✓ Loaded project config[/dim]")
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        raise SystemExit(1)

    env = load_env(project)

    # Validate required vars
    required = ["GCP_PROJECT_ID", "GCP_REGION", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)
    
    # Find which VM runs Forgejo (needed for multiple operations)
    vms_config = project_config_obj.get_vms()
    forgejo_vm_role = None
    forgejo_vm_index = 0
    
    for vm_role, vm_def in vms_config.items():
        services_list = vm_def.get("services", [])
        if "forgejo" in services_list:
            forgejo_vm_role = vm_role
            forgejo_vm_index = 0  # Use first instance of this VM role
            break

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
            tfvars_file = generate_tfvars(project_config_obj)

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
                project, project_config_obj, var_file=tfvars_file, auto_approve=True
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
                max_attempts = 18  # 18 * 10s = 180s max
                attempt = 0
                all_ready = False


                while attempt < max_attempts and not all_ready:
                    attempt += 1
                    console.print(f"  [dim]Attempt {attempt}/{max_attempts}...[/dim]")

                    ready_count = 0
                    for vm_key, ip in public_ips.items():
                        # Try SSH connection and sudo access
                        try:
                            result = subprocess.run(
                                f"ssh -i ~/.ssh/superdeploy_deploy -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes superdeploy@{ip} 'sudo -n whoami' 2>&1",
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )

                            # Check if sudo actually worked (should return "root")
                            if result.returncode == 0 and "root" in result.stdout:
                                ready_count += 1
                                console.print(
                                    f"    [green]✓[/green] {vm_key} ({ip}) ready"
                                )
                            else:
                                console.print(
                                    f"    [yellow]⏳[/yellow] {vm_key} ({ip}) not ready yet (sudo: {result.stdout.strip()[:50]})"
                                )
                        except Exception:
                            console.print(
                                f"    [yellow]⏳[/yellow] {vm_key} ({ip}) not reachable yet..."
                            )

                    if ready_count == len(public_ips):
                        all_ready = True
                        console.print("[green]✅ All VMs ready![/green]")
                    else:
                        if attempt < max_attempts:
                            console.print(
                                "  [dim]Waiting 10s before next check...[/dim]"
                            )
                            time.sleep(10)

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
    generate_ansible_inventory(env, ansible_dir, project)

    # Clean SSH known_hosts with NEW IPs
    clean_ssh_known_hosts(env)

    # Ansible (outside progress context to avoid output mixing)
    if not skip_ansible:
        console.print("\n[cyan]⚙️  Configuring services (Ansible)...[/cyan]")

        ansible_dir = project_root / "shared" / "ansible"

        # Prepare environment variables for Ansible
        # Get values from project config (NO HARDCODING!)
        forgejo_config = project_config_obj.get_infrastructure().get("forgejo", {})
        forgejo_org = forgejo_config.get("org", "")
        forgejo_admin_user = forgejo_config.get("admin_user", "admin")
        forgejo_admin_email = forgejo_config.get(
            "admin_email", f"admin@{project}.local"
        )

        # Build ansible_env_vars dynamically from all env vars
        ansible_env_vars = {
            "FORGEJO_ADMIN_USER": forgejo_admin_user,
            "FORGEJO_ADMIN_PASSWORD": env.get("FORGEJO_ADMIN_PASSWORD", ""),
            "FORGEJO_ADMIN_EMAIL": forgejo_admin_email,
            "FORGEJO_ORG": forgejo_org,
            "FORGEJO_REPO": env.get("FORGEJO_REPO", "superdeploy"),
            "forgejo_admin_user": forgejo_admin_user,
            "forgejo_admin_password": env.get("FORGEJO_ADMIN_PASSWORD", ""),
            "forgejo_admin_email": forgejo_admin_email,
            "forgejo_org": forgejo_org,
            "forgejo_db_name": forgejo_config.get("db_name", "forgejo"),
            "forgejo_db_user": forgejo_config.get("db_user", "forgejo"),
            "forgejo_db_password": env.get("FORGEJO_DB_PASSWORD", ""),
            "DOCKER_USERNAME": env.get("DOCKER_USERNAME", ""),
            "DOCKER_TOKEN": env.get("DOCKER_TOKEN", ""),
            "superdeploy_root": str(project_root),
        }

        # Add all VM IPs to ansible env vars dynamically
        for key, value in env.items():
            if key.endswith("_EXTERNAL_IP") or key.endswith("_INTERNAL_IP"):
                # Convert to lowercase for ansible (e.g., CORE_0_EXTERNAL_IP -> core_0_external_ip)
                ansible_env_vars[key.lower()] = value

        # Get Ansible vars from ConfigLoader (includes enabled_addons, addon_configs, etc.)
        ansible_vars = project_config_obj.to_ansible_vars()

        # Filter addons based on --skip flags
        enabled_addons = ansible_vars.get("enabled_addons", [])
        filtered_addons = filter_addons(enabled_addons, skip, project)

        # Update ansible_vars with filtered addons
        ansible_vars["enabled_addons"] = filtered_addons

        # Display deployment plan
        display_deployment_plan(enabled_addons, filtered_addons, skip)

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
        )

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
            task3 = progress.add_task("[cyan]Pushing code...", total=2)

            # GitHub - Push superdeploy repo as backup
            github_token = env.get("GITHUB_TOKEN")
            if github_token and github_token != "your-github-token":
                # Add or update GitHub remote
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
                            f"https://{github_token}@github.com/cfkarakulak/superdeploy.git",
                        ],
                        check=False,  # Don't fail if remote exists
                        capture_output=True,
                        cwd=str(project_root),
                    )
                except:
                    pass

                run_command("git push -u github master", cwd=str(project_root))
                console.print("[green]✅ Superdeploy backed up to GitHub![/green]")

            progress.advance(task3)

            # Push to Forgejo (needed for workflows)
            import urllib.parse

            # Reload env again in case IPs changed late
            env = load_env(project)

            # Get Forgejo host from VM config (already found at function start)
            forgejo_host = None
            if forgejo_vm_role:
                forgejo_ip_var = f"{forgejo_vm_role.upper()}_{forgejo_vm_index}_EXTERNAL_IP"
                forgejo_host = env.get(forgejo_ip_var)

            if not forgejo_host:
                console.print("[red]❌ No VM found for Forgejo connection[/red]")
            else:
                # Wait until Forgejo is reachable
                for _ in range(30):  # up to ~150s
                    try:
                        reachable = (
                            subprocess.run(
                                [
                                    "bash",
                                    "-lc",
                                    f"curl -sSf -m 3 http://{forgejo_host}:3001/ >/dev/null",
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

                encoded_pass = urllib.parse.quote(env["FORGEJO_ADMIN_PASSWORD"])
                repo_name = env.get("FORGEJO_REPO", "superdeploy")
                forgejo_url = (
                    f"http://{env['FORGEJO_ADMIN_USER']}:{encoded_pass}"
                    f"@{forgejo_host}:3001/{env['FORGEJO_ORG']}/{repo_name}.git"
                )

                # Force update Forgejo remote
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
                    console.print(
                        f"[yellow]⚠️  Failed to add Forgejo remote: {result.stderr}[/yellow]"
                    )

                # Push workflows to Forgejo
                try:
                    run_command(
                        "git push forgejo master:master -f", cwd=str(project_root)
                    )
                    console.print("[green]✅ Workflows pushed to Forgejo![/green]")
                except Exception as e:
                    console.print(
                        f"[yellow]⚠️  Forgejo push failed (may already exist): {e}[/yellow]"
                    )

            progress.advance(task3)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Infrastructure Deployed![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")

    # Find Forgejo host IP dynamically from project config
    forgejo_host = None
    if forgejo_vm_role:  # Already found earlier in the code
        forgejo_ip_var = f"{forgejo_vm_role.upper()}_{forgejo_vm_index}_EXTERNAL_IP"
        forgejo_host = env.get(forgejo_ip_var)

    if forgejo_host:
        console.print(f"\n[cyan]🌐 Forgejo:[/cyan] http://{forgejo_host}:3001")
        console.print(
            f"[cyan]👤 Login:[/cyan]   {env.get('FORGEJO_ADMIN_USER', 'admin')} / {env.get('FORGEJO_ADMIN_PASSWORD', '')}"
        )

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
