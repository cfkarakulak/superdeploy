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

console = Console()


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


def update_ips_in_env(project_root, env_file_path):
    """Extract VM IPs from Terraform and update .env"""
    console.print("[cyan]📍 Extracting VM IPs...[/cyan]")

    terraform_dir = project_root / "shared" / "terraform"

    # Get IPs from Terraform
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

        scrape_ext = subprocess.run(
            "terraform output -json vm_scrape_public_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        scrape_int = subprocess.run(
            "terraform output -json vm_scrape_internal_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        proxy_ext = subprocess.run(
            "terraform output -json vm_proxy_public_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        proxy_int = subprocess.run(
            "terraform output -json vm_proxy_internal_ips | jq -r '.[0]'",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Update .env file
        with open(env_file_path, "r") as f:
            lines = f.readlines()

        with open(env_file_path, "w") as f:
            for line in lines:
                if line.startswith("CORE_EXTERNAL_IP="):
                    f.write(f"CORE_EXTERNAL_IP={core_ext}\n")
                elif line.startswith("CORE_INTERNAL_IP="):
                    f.write(f"CORE_INTERNAL_IP={core_int}\n")
                elif line.startswith("SCRAPE_EXTERNAL_IP="):
                    f.write(f"SCRAPE_EXTERNAL_IP={scrape_ext}\n")
                elif line.startswith("SCRAPE_INTERNAL_IP="):
                    f.write(f"SCRAPE_INTERNAL_IP={scrape_int}\n")
                elif line.startswith("PROXY_EXTERNAL_IP="):
                    f.write(f"PROXY_EXTERNAL_IP={proxy_ext}\n")
                elif line.startswith("PROXY_INTERNAL_IP="):
                    f.write(f"PROXY_INTERNAL_IP={proxy_int}\n")
                else:
                    f.write(line)

        console.print("[green]✅ Updated IPs:[/green]")
        console.print(f"  CORE:   {core_ext} ({core_int})")
        console.print(f"  SCRAPE: {scrape_ext} ({scrape_int})")
        console.print(f"  PROXY:  {proxy_ext} ({proxy_int})")

        return True
    except Exception as e:
        console.print(f"[red]❌ Failed to extract IPs: {e}[/red]")
        return False


def generate_ansible_inventory(env, ansible_dir):
    """Generate Ansible inventory file"""
    inventory_content = f"""[core]
vm-core-1 ansible_host={env["CORE_EXTERNAL_IP"]} ansible_user={env.get("SSH_USER", "superdeploy")}

[scrape]
vm-scrape-1 ansible_host={env["SCRAPE_EXTERNAL_IP"]} ansible_user={env.get("SSH_USER", "superdeploy")}

[proxy]
vm-proxy-1 ansible_host={env["PROXY_EXTERNAL_IP"]} ansible_user={env.get("SSH_USER", "superdeploy")}
"""

    inventory_path = ansible_dir / "inventories" / "dev.ini"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_path, "w") as f:
        f.write(inventory_content)

    console.print("[green]✅ Ansible inventory generated[/green]")


def clean_ssh_known_hosts(env):
    """Clean SSH known_hosts to avoid conflicts"""
    console.print("[cyan]🔐 Cleaning SSH known_hosts...[/cyan]")

    for ip in [
        env.get("CORE_EXTERNAL_IP"),
        env.get("SCRAPE_EXTERNAL_IP"),
        env.get("PROXY_EXTERNAL_IP"),
    ]:
        if ip:
            subprocess.run(["ssh-keygen", "-R", ip], capture_output=True)

    console.print("[green]✅ SSH known_hosts cleaned[/green]")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform provisioning")
@click.option("--skip-ansible", is_flag=True, help="Skip Ansible configuration")
@click.option("--skip-git-push", is_flag=True, help="Skip Git push")
@click.option("--skip-sync", is_flag=True, help="Skip automatic GitHub secrets sync")
def up(project, skip_terraform, skip_ansible, skip_git_push, skip_sync):
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

    env = load_env()
    project_root = get_project_root()

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
            run_command("./terraform-wrapper.sh init", cwd=terraform_dir)
            progress.advance(task1)

            # Apply
            run_command("./terraform-wrapper.sh apply -auto-approve", cwd=terraform_dir)
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
    env_file_path = project_root / ".env"
    update_ips_in_env(project_root, env_file_path)

    # Reload env (in case IPs changed from Terraform)
    env = load_env()

    # Generate inventory with NEW IPs
    ansible_dir = project_root / "shared" / "ansible"
    generate_ansible_inventory(env, ansible_dir)

    # Clean SSH known_hosts with NEW IPs
    clean_ssh_known_hosts(env)

    # Ansible (outside progress context to avoid output mixing)
    if not skip_ansible:
        console.print("\n[cyan]⚙️  Configuring services (Ansible)...[/cyan]")

        ansible_dir = project_root / "shared" / "ansible"

        ansible_cmd = f"""
cd {ansible_dir} && \
SUPERDEPLOY_ROOT={project_root} ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,infrastructure,git-server \
  -e "core_external_ip={env["CORE_EXTERNAL_IP"]}" \
  -e "core_internal_ip={env["CORE_INTERNAL_IP"]}" \
  -e "scrape_external_ip={env.get("SCRAPE_EXTERNAL_IP", "")}" \
  -e "scrape_internal_ip={env.get("SCRAPE_INTERNAL_IP", "")}" \
  -e "proxy_external_ip={env.get("PROXY_EXTERNAL_IP", "")}" \
  -e "proxy_internal_ip={env.get("PROXY_INTERNAL_IP", "")}" \
  -e "FORGEJO_ADMIN_USER={env["FORGEJO_ADMIN_USER"]}" \
  -e "FORGEJO_ADMIN_PASSWORD={env["FORGEJO_ADMIN_PASSWORD"]}" \
  -e "FORGEJO_ADMIN_EMAIL={env["FORGEJO_ADMIN_EMAIL"]}" \
  -e "FORGEJO_ORG={env["FORGEJO_ORG"]}" \
  -e "REPO_SUPERDEPLOY={env["REPO_SUPERDEPLOY"]}" \
  -e "forgejo_admin_user={env["FORGEJO_ADMIN_USER"]}" \
  -e "forgejo_admin_password={env["FORGEJO_ADMIN_PASSWORD"]}" \
  -e "forgejo_admin_email={env["FORGEJO_ADMIN_EMAIL"]}" \
  -e "forgejo_org={env["FORGEJO_ORG"]}" \
  -e "forgejo_db_name=forgejo" \
  -e "forgejo_db_user=forgejo" \
  -e "forgejo_db_password={env["FORGEJO_DB_PASSWORD"]}" \
  -e "GRAFANA_ADMIN_USER={env["GRAFANA_ADMIN_USER"]}" \
  -e "GRAFANA_ADMIN_PASSWORD={env["GRAFANA_ADMIN_PASSWORD"]}" \
  -e "SMTP_USERNAME={env.get("SMTP_USERNAME", "")}" \
  -e "SMTP_PASSWORD={env.get("SMTP_PASSWORD", "")}" \
  -e "ALERT_EMAIL={env.get("ALERT_EMAIL", "")}" \
  -e "DOCKER_USERNAME={env.get("DOCKER_USERNAME", "")}" \
  -e "DOCKER_TOKEN={env.get("DOCKER_TOKEN", "")}" \
  -e "project_name={project}"
"""

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
                        cwd=project_root,
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
                        cwd=project_root,
                    )
                except:
                    pass

                run_command("git push -u github master", cwd=project_root)
                console.print("[green]✅ Superdeploy backed up to GitHub![/green]")

            progress.advance(task3)

            # Push to Forgejo (needed for workflows)
            import urllib.parse

            # Reload env again in case IPs changed late
            env = load_env()

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
                            cwd=project_root,
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
                cwd=project_root,
            )

            result = subprocess.run(
                ["git", "remote", "add", "forgejo", forgejo_url],
                capture_output=True,
                text=True,
                cwd=project_root,
            )

            if result.returncode != 0:
                console.print(
                    f"[yellow]⚠️  Failed to add Forgejo remote: {result.stderr}[/yellow]"
                )

            # Push workflows to Forgejo
            try:
                run_command("git push forgejo master:master -f", cwd=project_root)
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
        console.print(
            "\n[bold cyan]🔄 Auto-syncing GitHub secrets (new IPs)...[/bold cyan]"
        )

        # Direct sync call with proper error handling
        try:
            sync_cmd = [
                "superdeploy",
                "sync:infra",
                "-p",
                project,
            ]

            result = subprocess.run(
                sync_cmd, capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                console.print("[green]✅ GitHub secrets synced![/green]")
            else:
                console.print(
                    "[yellow]⚠️  Sync had issues (check output above)[/yellow]"
                )
                if result.stderr:
                    console.print(f"[dim]{result.stderr[:500]}[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Sync failed: {e}[/yellow]")
            console.print(
                f"[dim]Run 'superdeploy sync:infra -p {project}' manually to update GitHub secrets[/dim]"
            )
    else:
        console.print(
            f"\n[yellow]Note:[/yellow] Run [bold cyan]superdeploy sync:infra -p {project}[/bold cyan] to configure GitHub secrets"
        )
