#!/usr/bin/env python3
"""
Dynamic Ansible inventory for SuperDeploy multi-project support

Reads Terraform state for each project workspace and generates
inventory with project-based groups.

Usage:
    # List all hosts
    ./dynamic.py --list
    
    # Get specific host vars
    ./dynamic.py --host <hostname>
    
    # Use with ansible-playbook
    ansible-playbook -i inventories/dynamic.py playbooks/site.yml --limit project_cheapa

Output format:
{
  "project_cheapa": {
    "hosts": ["cheapa-core-1"],
    "vars": {
      "project_name": "cheapa",
      "ansible_user": "superdeploy"
    }
  },
  "project_projectx": {
    "hosts": ["projectx-core-1"],
    "vars": {
      "project_name": "projectx",
      "ansible_user": "superdeploy"
    }
  },
  "_meta": {
    "hostvars": {
      "cheapa-core-1": {
        "ansible_host": "1.2.3.4",
        "ansible_user": "superdeploy",
        "project_name": "cheapa"
      }
    }
  }
}
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List


def get_terraform_dir() -> Path:
    """Get the Terraform directory path"""
    script_dir = Path(__file__).parent
    return script_dir.parent.parent / "terraform"


def run_terraform_command(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """
    Run a Terraform command
    
    Args:
        args: Command arguments
        cwd: Working directory
        
    Returns:
        CompletedProcess instance
    """
    cmd = ["terraform"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result


def list_workspaces(terraform_dir: Path) -> List[str]:
    """
    List all Terraform workspaces
    
    Args:
        terraform_dir: Path to Terraform directory
        
    Returns:
        List of workspace names (excluding 'default')
    """
    result = run_terraform_command(["workspace", "list"], terraform_dir)
    
    if result.returncode != 0:
        return []
    
    workspaces = []
    for line in result.stdout.split('\n'):
        # Remove asterisk and whitespace
        workspace = line.strip().replace('*', '').strip()
        if workspace and workspace != 'default':
            workspaces.append(workspace)
    
    return workspaces


def get_terraform_outputs(workspace: str, terraform_dir: Path) -> Dict[str, Any]:
    """
    Get Terraform outputs for a specific workspace
    
    Args:
        workspace: Workspace name
        terraform_dir: Path to Terraform directory
        
    Returns:
        Dictionary of Terraform outputs
    """
    # Select workspace
    result = run_terraform_command(
        ["workspace", "select", workspace],
        terraform_dir
    )
    
    if result.returncode != 0:
        return {}
    
    # Get outputs as JSON
    result = run_terraform_command(
        ["output", "-json"],
        terraform_dir
    )
    
    if result.returncode != 0 or not result.stdout:
        return {}
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def extract_vm_info(outputs: Dict[str, Any], project_name: str) -> List[Dict[str, Any]]:
    """
    Extract VM information from Terraform outputs
    
    Args:
        outputs: Terraform outputs dictionary
        project_name: Name of the project
        
    Returns:
        List of VM info dictionaries with name, ip, and role
    """
    vms = []
    
    # Look for external IP outputs
    # Expected format: {role}_external_ip or {role}_{index}_external_ip
    for key, value in outputs.items():
        if not key.endswith('_external_ip'):
            continue
        
        # Extract the actual IP value
        ip = value.get('value') if isinstance(value, dict) else value
        if not ip:
            continue
        
        # Extract role from key (e.g., "core_external_ip" -> "core")
        role = key.replace('_external_ip', '')
        
        # Generate hostname
        # If the role already contains the project name, use it as-is
        # Otherwise, prefix with project name
        if role.startswith(f"{project_name}-"):
            hostname = role
        else:
            hostname = f"{project_name}-{role}"
        
        vms.append({
            'name': hostname,
            'ip': ip,
            'role': role.split('-')[-1] if '-' in role else role,
            'project': project_name
        })
    
    return vms


def generate_inventory() -> Dict[str, Any]:
    """
    Generate dynamic inventory from Terraform workspaces
    
    Returns:
        Ansible inventory dictionary
    """
    terraform_dir = get_terraform_dir()
    
    # Check if Terraform directory exists
    if not terraform_dir.exists():
        return {
            "_meta": {
                "hostvars": {}
            }
        }
    
    # List workspaces
    workspaces = list_workspaces(terraform_dir)
    
    inventory = {
        "_meta": {
            "hostvars": {}
        }
    }
    
    # Generate inventory for each project workspace
    for project_name in workspaces:
        outputs = get_terraform_outputs(project_name, terraform_dir)
        
        if not outputs:
            continue
        
        # Extract VM information
        vms = extract_vm_info(outputs, project_name)
        
        if not vms:
            continue
        
        # Create project group
        group_name = f"project_{project_name}"
        hosts = []
        
        for vm in vms:
            hostname = vm['name']
            hosts.append(hostname)
            
            # Add host variables
            inventory["_meta"]["hostvars"][hostname] = {
                "ansible_host": vm['ip'],
                "ansible_user": "superdeploy",
                "ansible_ssh_common_args": "-o StrictHostKeyChecking=no",
                "project_name": project_name,
                "vm_role": vm['role']
            }
        
        # Add project group
        inventory[group_name] = {
            "hosts": hosts,
            "vars": {
                "project_name": project_name,
                "ansible_user": "superdeploy"
            }
        }
    
    return inventory


def get_host_vars(hostname: str) -> Dict[str, Any]:
    """
    Get variables for a specific host
    
    Args:
        hostname: Name of the host
        
    Returns:
        Dictionary of host variables
    """
    inventory = generate_inventory()
    return inventory.get("_meta", {}).get("hostvars", {}).get(hostname, {})


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Dynamic Ansible inventory for SuperDeploy"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all hosts"
    )
    parser.add_argument(
        "--host",
        help="Get variables for a specific host"
    )
    
    args = parser.parse_args()
    
    if args.list:
        inventory = generate_inventory()
        print(json.dumps(inventory, indent=2))
    elif args.host:
        host_vars = get_host_vars(args.host)
        print(json.dumps(host_vars, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
