"""
Project deployment commands
"""

from pathlib import Path
from rich.console import Console
from cli.ui_components import show_header
import click

console = Console()


@click.command(name="projects:deploy")
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--services",
    "-s",
    default="all",
    help="Services to deploy (comma-separated or 'all')",
)
def projects_deploy(project, services):
    """Deploy project-specific services to VM"""

    show_header(
        title="Deploy Project",
        project=project,
        details={"Services": services},
        console=console,
    )

    project_root = Path(__file__).parents[2]
    project_path = project_root / "projects" / project

    if not project_path.exists():
        console.print(f"[red]❌ Project '{project}' not found at {project_path}[/red]")
        return

    # Load project secrets from secrets.yml
    from cli.secret_manager import SecretManager
    from cli.utils import get_project_root

    project_root = get_project_root()
    secret_mgr = SecretManager(project_root, project)

    try:
        secrets_data = secret_mgr.load_secrets()
    except FileNotFoundError:
        console.print(
            f"[red]❌ Project secrets not found: {project_path / 'secrets.yml'}[/red]"
        )
        console.print(f"[dim]Run: superdeploy init -p {project}[/dim]")
        return

    # Extract all secrets (shared + app-specific)
    project_secrets = {}
    if secrets_data.get("secrets", {}).get("shared"):
        project_secrets.update(secrets_data["secrets"]["shared"])

    # Add app-specific secrets
    for app_name, app_secrets in secrets_data.get("secrets", {}).items():
        if app_name != "shared" and isinstance(app_secrets, dict):
            project_secrets.update(app_secrets)

    # Run Ansible playbook for project deployment
    ansible_dir = project_root / "shared" / "ansible"
    ansible_playbook = ansible_dir / "playbooks" / "project_deploy.yml"

    if not ansible_playbook.exists():
        console.print("[yellow]Creating project deployment playbook...[/yellow]")
        _create_project_deploy_playbook(ansible_dir)

    # Build ansible extra vars dynamically from project secrets
    extra_vars = [f'-e "project_name={project}"']

    # Add all secret variables dynamically (no hardcoded addon names)
    for key, value in project_secrets.items():
        if value:  # Only add non-empty values
            # Convert to ansible var format (e.g., POSTGRES_PASSWORD -> project_postgres_password)
            ansible_var = f"project_{key.lower()}"
            extra_vars.append(f'-e "{ansible_var}={value}"')

    extra_vars_str = " \\\n  ".join(extra_vars)

    ansible_cmd = f"""
cd {ansible_dir} && \\
ansible-playbook -i inventories/dev.ini playbooks/project_deploy.yml \\
  {extra_vars_str}
"""

    # Run ansible with clean tree view
    from cli.ansible_runner import AnsibleRunner
    from cli.logger import DeployLogger

    verbose = False  # Can be made a CLI option later
    with DeployLogger("project", project, verbose=verbose) as logger:
        logger.step("Deploying project services")

        runner = AnsibleRunner(logger, title=f"Deploying {project}", verbose=verbose)
        returncode = runner.run(ansible_cmd, cwd=project_root)

        if returncode != 0:
            logger.log_error("Deployment failed", context="Check logs for details")
            raise SystemExit(1)

        logger.success("Project deployed successfully")
        console.print(f"\n[green]✅ Project '{project}' deployed successfully![/green]")
        console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")


def _create_project_deploy_playbook(ansible_dir):
    """Create generic project deployment playbook"""
    playbook_path = ansible_dir / "playbooks" / "project_deploy.yml"
    playbook_content = """---
- name: Deploy Project to VM
  hosts: core
  become: yes
  vars:
    project_name: "{{ project_name }}"
    project_path: "/opt/apps/{{ project_name }}"
  
  tasks:
    - name: Create project directories
      file:
        path: "{{ item }}"
        state: directory
        owner: superdeploy
        group: superdeploy
        mode: '0755'
      loop:
        - "{{ project_path }}"
        - "{{ project_path }}/compose"
        - "{{ project_path }}/provision"

    - name: Sync project compose files
      synchronize:
        src: "{{ playbook_dir }}/../../projects/{{ project_name }}/compose/"
        dest: "{{ project_path }}/compose/"
        delete: no
        recursive: yes
        rsync_opts:
          - "--exclude=secrets.yml"
          - "--exclude=*.log"

    - name: Sync project provision files (if exists)
      synchronize:
        src: "{{ playbook_dir }}/../../projects/{{ project_name }}/provision/"
        dest: "{{ project_path }}/provision/"
        delete: no
        recursive: yes
      ignore_errors: yes

    - name: Fix ownership
      file:
        path: "{{ project_path }}"
        owner: superdeploy
        group: superdeploy
        recurse: yes

    - name: Copy project monitoring configs (Prometheus targets)
      copy:
        src: "{{ project_path }}/provision/prometheus/targets.yml"
        dest: "/opt/superdeploy/shared/prometheus/projects/{{ project_name }}.yml"
        owner: superdeploy
        group: superdeploy
        mode: '0644'
        remote_src: yes
      ignore_errors: yes

    - name: Copy project alerts
      copy:
        src: "{{ playbook_dir }}/../../projects/{{ project_name }}/monitoring/alerts.yml"
        dest: "/opt/superdeploy/shared/prometheus/rules/{{ project_name }}.yml"
        owner: superdeploy
        group: superdeploy
        mode: '0644'
      ignore_errors: yes

    - name: Copy project Caddy routes
      copy:
        src: "{{ project_path }}/provision/caddy/routes.caddy"
        dest: "/opt/superdeploy/shared/caddy/routes/{{ project_name }}.caddy"
        owner: superdeploy
        group: superdeploy
        mode: '0644'
        remote_src: yes
      ignore_errors: yes

    - name: Reload Caddy config
      shell: docker exec superdeploy-caddy caddy reload --config /etc/caddy/Caddyfile
      ignore_errors: yes

    - name: Reload Prometheus config
      shell: curl -X POST http://localhost:9090/-/reload
      ignore_errors: yes

    - name: Display deployment status
      debug:
        msg: "Project '{{ project_name }}' files deployed. Use Forgejo workflow to start services."
"""

    playbook_path.write_text(playbook_content)
    console.print(f"[green]✅ Created {playbook_path}[/green]")
