"""
Project deployment commands
"""

from cli.base import ProjectCommand
import click


class ProjectsDeployCommand(ProjectCommand):
    """Deploy project-specific services to VM."""

    def __init__(self, project_name: str, services: str = "all", verbose: bool = False, json_output: bool = False):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.services = services

    def execute(self) -> None:
        """Execute projects:deploy command."""
        self.show_header(
            title="Deploy Project",
            project=self.project_name,
            details={"Services": self.services},
        )

        # Load project secrets from database
        from cli.secret_manager import SecretManager

        project_path = self.project_root / "projects" / self.project_name

        if not project_path.exists():
            self.console.print(
                f"[red]❌ Project '{self.project_name}' not found at {project_path}[/red]"
            )
            return

        secret_mgr = SecretManager(self.project_root, self.project_name, "production")

        try:
            secrets_data = secret_mgr.load_secrets()
        except Exception:
            self.console.print(
                f"[red]❌ Project secrets not found in database[/red]"
            )
            self.console.print(f"[dim]Run: superdeploy {self.project_name}:init[/dim]")
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
        ansible_dir = self.project_root / "shared" / "ansible"
        ansible_playbook = ansible_dir / "playbooks" / "project_deploy.yml"

        if not ansible_playbook.exists():
            self.console.print(
                "[yellow]Creating project deployment playbook...[/yellow]"
            )
            _create_project_deploy_playbook(ansible_dir, self.console)

        # Build ansible extra vars dynamically from project secrets
        extra_vars = [f'-e "project_name={self.project_name}"']

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

        with DeployLogger("project", self.project_name, verbose=self.verbose) as logger:
            if logger:
                logger.step("Deploying project services")

            runner = AnsibleRunner(
                logger,
                title=f"Deploying {self.project_name}",
                verbose=self.verbose,
            )
            returncode = runner.run(ansible_cmd, cwd=self.project_root)

            if returncode != 0:
                if logger:
                    logger.log_error("Deployment failed", context="Check logs for details")
                raise SystemExit(1)

            if logger:

                logger.success("Project deployed successfully")
            self.console.print(
                f"\n[green]✅ Project '{self.project_name}' deployed successfully![/green]"
            )
            self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")


def _create_project_deploy_playbook(ansible_dir, console):
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
        msg: "Project '{{ project_name }}' files deployed. Push to GitHub to trigger deployment."
"""

    playbook_path.write_text(playbook_content)
    console.print(f"[green]✅ Created {playbook_path}[/green]")


@click.command(name="projects:deploy")
@click.option(
    "--services",
    "-s",
    default="all",
    help="Services to deploy (comma-separated or 'all')",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def projects_deploy(project, services, verbose, json_output):
    """Deploy project-specific services to VM"""
    cmd = ProjectsDeployCommand(project, services=services, verbose=verbose, json_output=json_output)
    cmd.run()
