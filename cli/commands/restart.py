"""SuperDeploy CLI - Restart command"""

import click
from rich.console import Console
from cli.utils import get_project_root
from cli.core.config_loader import ConfigLoader
from cli.ansible_utils import run_ansible_playbook

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
def restart(project, app):
    """
    Restart an application container
    
    \b
    Example:
      superdeploy restart -p cheapa -a api
    """
    console.print(f"\n[cyan]🔄 Restarting {project}/{app}...[/cyan]\n")
    
    project_root = get_project_root()
    projects_dir = project_root / "projects"
    
    # Load config to find VM
    try:
        config_loader = ConfigLoader(projects_dir)
        project_config = config_loader.load_project(project)
        apps = project_config.raw_config.get("apps", {})
        
        if app not in apps:
            console.print(f"[red]❌ App '{app}' not found in project config[/red]")
            return
        
        vm_role = apps[app].get("vm", "core")
        
    except Exception as e:
        console.print(f"[red]❌ Error loading config: {e}[/red]")
        return
    
    # Restart via Ansible
    console.print(f"[dim]Restarting on VM role: {vm_role}[/dim]\n")
    
    playbook_content = f"""---
- name: Restart {app}
  hosts: {vm_role}
  become: yes
  tasks:
    - name: Restart container
      community.docker.docker_container:
        name: "{project}-{app}"
        state: started
        restart: yes
      
    - name: Wait for container
      wait_for:
        timeout: 5
      
    - name: Show status
      command: docker ps --filter name={project}-{app} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'
      register: status
      
    - name: Display status
      debug:
        msg: "{{{{ status.stdout }}}}"
"""
    
    playbook_path = project_root / "shared" / "ansible" / "playbooks" / f"restart-{app}.yml"
    playbook_path.write_text(playbook_content)
    
    try:
        run_ansible_playbook(
            playbook_path=str(playbook_path),
            inventory_path=str(projects_dir / project / "inventory.ini"),
            extra_vars={"project_name": project}
        )
        console.print(f"\n[green]✅ {app} restarted successfully![/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Restart failed: {e}[/red]\n")
    finally:
        playbook_path.unlink(missing_ok=True)
