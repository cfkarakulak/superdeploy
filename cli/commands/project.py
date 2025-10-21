"""
Project deployment commands
"""

import subprocess
from pathlib import Path
from rich.console import Console
from dotenv import dotenv_values
import click

console = Console()


@click.group()
def project():
    """Manage project deployments"""
    pass


@project.command()
@click.option("--project", "-p", required=True, help="Project name (e.g., cheapa)")
@click.option(
    "--services",
    "-s",
    default="all",
    help="Services to deploy (comma-separated or 'all')",
)
def deploy(project, services):
    """Deploy project-specific services to VM"""

    project_root = Path(__file__).parents[2]
    project_path = project_root / "projects" / project

    if not project_path.exists():
        console.print(f"[red]❌ Project '{project}' not found at {project_path}[/red]")
        return

    console.print(f"\n[cyan]🚀 Deploying project: {project}[/cyan]\n")

    # Load infrastructure env
    env_file = project_root / ".env"
    env = dotenv_values(env_file)

    # Load project secrets
    project_secrets_file = project_path / "secrets.env"
    if not project_secrets_file.exists():
        console.print(
            f"[red]❌ Project secrets not found: {project_secrets_file}[/red]"
        )
        return

    project_secrets = dotenv_values(project_secrets_file)

    # Run Ansible playbook for project deployment
    ansible_dir = project_root / "shared" / "ansible"
    ansible_playbook = ansible_dir / "playbooks" / "project_deploy.yml"

    if not ansible_playbook.exists():
        console.print("[yellow]Creating project deployment playbook...[/yellow]")
        _create_project_deploy_playbook(ansible_dir)

    ansible_cmd = f"""
cd {ansible_dir} && \\
ansible-playbook -i inventories/dev.ini playbooks/project_deploy.yml \\
  -e "project_name={project}" \\
  -e "project_postgres_password={project_secrets.get("POSTGRES_PASSWORD", "")}" \\
  -e "project_rabbitmq_password={project_secrets.get("RABBITMQ_PASSWORD", "")}" \\
  -e "project_redis_password={project_secrets.get("REDIS_PASSWORD", "")}"
"""

    try:
        subprocess.run(ansible_cmd, shell=True, check=True)
        console.print(f"[green]✅ Project '{project}' deployed successfully![/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Deployment failed: {e}[/red]")


def _create_project_deploy_playbook(ansible_dir):
    """Create generic project deployment playbook"""
    playbook_path = ansible_dir / "playbooks" / "project_deploy.yml"
    playbook_content = """---
- name: Deploy Project to VM
  hosts: core
  become: yes
  vars:
    project_name: "{{ project_name }}"
    project_path: "/opt/superdeploy/projects/{{ project_name }}"
  
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
          - "--exclude=.env*"
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
