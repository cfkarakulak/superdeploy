"""Ansible runner for SuperDeploy"""

import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from rich.console import Console

console = Console()


class AnsibleRunner:
    """Run Ansible playbooks with proper inventory and variables"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ansible_dir = project_root / "shared" / "ansible"
        self.playbook_dir = self.ansible_dir / "playbooks"
        self.inventory_dir = self.ansible_dir / "inventories"
    
    def run_playbook(
        self,
        playbook: str,
        project_name: str,
        project_config: dict,
        extra_vars: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        skip_tags: Optional[List[str]] = None,
        limit: Optional[str] = None,
        check: bool = False
    ) -> bool:
        """
        Run an Ansible playbook
        
        Args:
            playbook: Playbook filename (e.g., 'site.yml')
            project_name: Name of the project
            project_config: Project configuration dictionary
            extra_vars: Additional variables to pass
            tags: List of tags to run
            skip_tags: List of tags to skip
            limit: Limit execution to specific hosts/groups
            check: Run in check mode (dry-run)
            
        Returns:
            True if successful, False otherwise
        """
        playbook_path = self.playbook_dir / playbook
        
        if not playbook_path.exists():
            console.print(f"[red]❌ Playbook not found: {playbook_path}[/red]")
            return False
        
        # Build command
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", str(self.inventory_dir / "dev.ini"),  # Use static inventory for now
        ]
        
        # Add limit (project-specific hosts)
        if limit:
            cmd.extend(["--limit", limit])
        elif project_name:
            # Limit to project-specific hosts
            cmd.extend(["--limit", "core"])  # For now, all projects use 'core' group
        
        # Add tags
        if tags:
            cmd.extend(["--tags", ",".join(tags)])
        
        # Add skip tags
        if skip_tags:
            cmd.extend(["--skip-tags", ",".join(skip_tags)])
        
        # Add check mode
        if check:
            cmd.append("--check")
        
        # Build extra vars
        all_vars = {
            "project_name": project_name,
            "project_config": project_config,
        }
        
        if extra_vars:
            all_vars.update(extra_vars)
        
        # Add extra vars as JSON
        import json
        cmd.extend(["--extra-vars", json.dumps(all_vars)])
        
        # Add verbose output
        cmd.append("-v")
        
        # Run command
        console.print(f"[dim]Running: {' '.join(cmd[:4])}...[/dim]")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.ansible_dir),
                check=True,
                capture_output=False,  # Show output in real-time
                text=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Ansible playbook failed with exit code {e.returncode}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Failed to run Ansible: {e}[/red]")
            return False
    
    def update_inventory(self, project_name: str, vm_ip: str, ssh_user: str = "superdeploy"):
        """
        Update static inventory file for a project
        
        Args:
            project_name: Name of the project
            vm_ip: VM IP address
            ssh_user: SSH username
        """
        inventory_file = self.inventory_dir / "dev.ini"
        
        # For now, we use a simple static inventory
        # In the future, we can generate project-specific inventories
        content = f"""[core]
vm-core-1 ansible_host={vm_ip} ansible_user={ssh_user}

[project_{project_name}:children]
core

[project_{project_name}:vars]
project_name={project_name}
"""
        
        inventory_file.write_text(content)
        console.print(f"[dim]✓ Updated inventory: {inventory_file}[/dim]")
