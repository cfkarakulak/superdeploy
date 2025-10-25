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
    get_project_path,
    validate_env_vars,
)
from cli.ansible_utils import build_ansible_command

console = Console()


def filter_addons(enabled_addons, start_from, skip_addons, project):
    """
    Filter addon list based on --start-from and --skip flags
    
    Args:
        enabled_addons: List of all enabled addons
        start_from: Addon name to start from (skip all before it)
        skip_addons: Tuple of addon names to skip
        project: Project name for error messages
        
    Returns:
        Filtered list of addons to deploy
    """
    if not enabled_addons:
        return []
    
    filtered = list(enabled_addons)
    
    # Apply --start-from filter
    if start_from:
        if start_from not in enabled_addons:
            console.print(f"[red]❌ Error: Addon '{start_from}' not found in project '{project}'[/red]")
            console.print(f"[yellow]Available addons: {', '.join(enabled_addons)}[/yellow]")
            raise SystemExit(1)
        
        # Find index and slice from that point
        start_index = enabled_addons.index(start_from)
        filtered = enabled_addons[start_index:]
        
        console.print(f"[yellow]⚠️  Starting from addon: {start_from}[/yellow]")
        console.print(f"[dim]Skipping: {', '.join(enabled_addons[:start_index])}[/dim]")
    
    # Apply --skip filter
    if skip_addons:
        skipped = []
        for addon in skip_addons:
            if addon in filtered:
                filtered.remove(addon)
                skipped.append(addon)
            elif addon not in enabled_addons:
                console.print(f"[yellow]⚠️  Warning: Addon '{addon}' not found in project (ignoring)[/yellow]")
        
        if skipped:
            console.print(f"[yellow]⚠️  Skipping addons: {', '.join(skipped)}[/yellow]")
    
    return filtered


def display_deployment_plan(all_addons, filtered_addons, start_from, skip_addons):
    """Display deployment plan showing which addons will be deployed"""
    if not all_addons:
        return
    
    console.print("\n[bold cyan]📋 Deployment Plan[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    
    for addon in all_addons:
        if addon in filtered_addons:
            console.print(f"  [green]✓[/green] {addon}")
        else:
            reason = ""
            if start_from and all_addons.index(addon) < all_addons.index(start_from):
                reason = f"[dim](before {start_from})[/dim]"
            elif skip_addons and addon in skip_addons:
                reason = "[dim](skipped)[/dim]"
            console.print(f"  [dim]○ {addon} {reason}[/dim]")
    
    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print(f"[cyan]Total: {len(filtered_addons)}/{len(all_addons)} addons will be deployed[/cyan]\n")


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
    """Extract VM IPs from Terraform and update project's .env"""
    console.print("[cyan]📍 Extracting VM IPs...[/cyan]")

    terraform_dir = project_root / "shared" / "terraform"
    env_file_path = project_root / "projects" / project_name / ".env"

    # Get IPs from Terraform (only core VM - project-specific)
    try:
        core_ext = subprocess.run(
            "terraform output -json vm_core_public_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        core_int = subprocess.run(
            "terraform output -json vm_core_internal_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Update or append IPs to .env file (only core VM)
        ip_vars = {
            'CORE_EXTERNAL_IP': core_ext,
            'CORE_INTERNAL_IP': core_int,
        }
        
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
        console.print(f"  CORE: {core_ext} ({core_int})")

        return True
    except Exception as e:
        console.print(f"[red]❌ Failed to extract IPs: {e}[/red]")
        return False


def generate_ansible_inventory(env, ansible_dir):
    """Generate Ansible inventory file (only core VM - project-specific)"""
    inventory_content = f"""[core]
vm-core-1 ansible_host={env["CORE_EXTERNAL_IP"]} ansible_user={env.get("SSH_USER", "superdeploy")}
"""

    inventory_path = ansible_dir / "inventories" / "dev.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)

    console.print("[green]✅ Ansible inventory generated[/green]")


def clean_ssh_known_hosts(env):
    """Clean SSH known_hosts to avoid conflicts (only core VM)"""
    console.print("[cyan]🔐 Cleaning SSH known_hosts...[/cyan]")

    core_ip = env.get("CORE_EXTERNAL_IP")
    if core_ip:
        subprocess.run(["ssh-keygen", "-R", core_ip], capture_output=True)

    console.print("[green]✅ SSH known_hosts cleaned[/green]")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-git-push", is_flag=True, help="Skip Git push")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
@click.option("--start-from", help="Start deployment from specific addon (skip previous addons)")
@click.option("--skip", multiple=True, help="Skip specific addon(s) during deployment")
def up(project, skip_terraform, skip_ansible, skip_git_push, skip_sync, start_from, skip):
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
            terraform_dir = project_root / "shared" / "terraform"
            # Add PROJECT_NAME to env for Terraform
            terraform_env = {**env, 'PROJECT_NAME': project}
            run_command("./terraform-wrapper.sh init", cwd=str(terraform_dir), env=terraform_env)
            progress.advance(task1)

            # Refresh state to sync with actual infrastructure
            try:
                run_command("./terraform-wrapper.sh refresh", cwd=str(terraform_dir), env=terraform_env)
            except Exception:
                # Refresh may fail if state is empty, that's ok
                pass

            # Apply
            run_command("./terraform-wrapper.sh apply -auto-approve", cwd=str(terraform_dir), env=terraform_env)
            progress.advance(task1)
            progress.advance(task1)

            console.print("[green]✅ VMs provisioned![/green]")

            # Wait for VMs
            task_wait = progress.add_task(
                "[yellow]Waiting for VMs to be ready (120s)...", total=120
            )
            for i in range(120):
                time.sleep(1)
                progress.advance(task_wait)
            console.print("[green]✅ VMs ready![/green]")

    # Update IPs from Terraform (even if skipped, read current state)
    update_ips_in_env(project_root, project)

    # Reload env (in case IPs changed from Terraform)
    env = load_env(project)

    # Generate inventory with NEW IPs
    ansible_dir = project_root / "shared" / "ansible"
    generate_ansible_inventory(env, ansible_dir)

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

        # Load generated passwords from .passwords.yml
        project_path = get_project_path(project)
        passwords_file = project_path / ".passwords.yml"
        generated_passwords = {}

        if passwords_file.exists():
            import yaml

            with open(passwords_file) as f:
                passwords_data = yaml.safe_load(f)
                if passwords_data and "passwords" in passwords_data:
                    # Flatten the nested structure
                    for addon_name, addon_passwords in passwords_data[
                        "passwords"
                    ].items():
                        for var_name, var_data in addon_passwords.items():
                            if isinstance(var_data, dict):
                                generated_passwords[var_name] = var_data.get(
                                    "value", ""
                                )
                            else:
                                generated_passwords[var_name] = var_data

        ansible_env_vars = {
            "core_external_ip": env["CORE_EXTERNAL_IP"],
            "core_internal_ip": env["CORE_INTERNAL_IP"],
            "FORGEJO_ADMIN_USER": forgejo_admin_user,
            "FORGEJO_ADMIN_PASSWORD": generated_passwords.get(
                "FORGEJO_ADMIN_PASSWORD", ""
            ),
            "FORGEJO_ADMIN_EMAIL": forgejo_admin_email,
            "FORGEJO_ORG": forgejo_org,
            "REPO_SUPERDEPLOY": env.get("REPO_SUPERDEPLOY", "superdeploy"),
            "forgejo_admin_user": forgejo_admin_user,
            "forgejo_admin_password": generated_passwords.get(
                "FORGEJO_ADMIN_PASSWORD", ""
            ),
            "forgejo_admin_email": forgejo_admin_email,
            "forgejo_org": forgejo_org,
            "forgejo_db_name": forgejo_config.get("db_name", "forgejo"),
            "forgejo_db_user": forgejo_config.get("db_user", "forgejo"),
            "forgejo_db_password": generated_passwords.get("FORGEJO_DB_PASSWORD", ""),
            "DOCKER_USERNAME": env.get("DOCKER_USERNAME", ""),
            "DOCKER_TOKEN": env.get("DOCKER_TOKEN", ""),
            "superdeploy_root": str(project_root),
        }

        # Get Ansible vars from ConfigLoader (includes enabled_addons, addon_configs, etc.)
        ansible_vars = project_config_obj.to_ansible_vars()
        
        # Filter addons based on --start-from and --skip flags
        enabled_addons = ansible_vars.get("enabled_addons", [])
        filtered_addons = filter_addons(enabled_addons, start_from, skip, project)
        
        # Update ansible_vars with filtered addons
        ansible_vars["enabled_addons"] = filtered_addons
        
        # Display deployment plan
        display_deployment_plan(enabled_addons, filtered_addons, start_from, skip)
        
        # Build Ansible command using shared utility
        ansible_cmd = build_ansible_command(
            ansible_dir=ansible_dir,
            project_root=project_root,
            project_config=ansible_vars,
            env_vars=ansible_env_vars,
            tags="foundation,addons,project",
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

            # Wait until Forgejo is reachable
            forgejo_host = env["CORE_EXTERNAL_IP"]
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
            repo_name = env.get("REPO_SUPERDEPLOY", "superdeploy")
            forgejo_url = (
                f"http://{env['FORGEJO_ADMIN_USER']}:{encoded_pass}"
                f"@{env['CORE_EXTERNAL_IP']}:3001/{env['FORGEJO_ORG']}/{repo_name}.git"
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
                run_command("git push forgejo master:master -f", cwd=str(project_root))
                console.print("[green]✅ Workflows pushed to Forgejo![/green]")
            except Exception as e:
                console.print(
                    f"[yellow]⚠️  Forgejo push failed (may already exist): {e}[/yellow]"
                )

            progress.advance(task3)

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]🎉 Infrastructure Deployed![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(f"\n[cyan]🌐 Forgejo:[/cyan] http://{env['CORE_EXTERNAL_IP']}:3001")
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
