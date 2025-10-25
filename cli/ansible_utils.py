"""SuperDeploy CLI - Ansible utility functions"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()


def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def generate_ansible_extra_vars(project_config, env_vars=None, project_root=None):
    """
    Generate Ansible extra vars from project configuration
    
    Args:
        project_config (dict): Project configuration from ConfigLoader.to_ansible_vars()
        env_vars (dict): Optional environment variables to include
        project_root (Path): Root directory of superdeploy
    
    Returns:
        dict: Dictionary of extra vars for Ansible
    """
    # Start with project_config which already has most fields from to_ansible_vars()
    extra_vars = project_config.copy()
    
    # Set addons source path explicitly
    if project_root:
        extra_vars['addons_source_path'] = str(project_root / 'addons')
        
        # Load project secrets from .passwords.yml if it exists
        passwords_file = project_root / 'projects' / project_config['project_name'] / '.passwords.yml'
        if passwords_file.exists():
            with open(passwords_file) as f:
                passwords_data = yaml.safe_load(f)
                # Flatten the passwords structure for easier access in Ansible
                flattened_secrets = {}
                for addon_name, addon_passwords in passwords_data.get('passwords', {}).items():
                    for secret_name, secret_data in addon_passwords.items():
                        if isinstance(secret_data, dict) and 'value' in secret_data:
                            flattened_secrets[secret_name] = secret_data['value']
                        else:
                            flattened_secrets[secret_name] = secret_data
                extra_vars['project_secrets'] = flattened_secrets
        else:
            extra_vars['project_secrets'] = {}
    else:
        extra_vars['project_secrets'] = {}
    
    # Extract convenience vars from nested config
    network_config = extra_vars.get('network_config', {})
    if network_config:
        extra_vars['network_subnet'] = network_config.get('subnet', '172.20.0.0/24')
    
    monitoring_config = extra_vars.get('monitoring', {})
    if monitoring_config:
        extra_vars['monitoring_enabled'] = monitoring_config.get('enabled', False)
        extra_vars['prometheus_enabled'] = monitoring_config.get('prometheus', False)
        extra_vars['grafana_enabled'] = monitoring_config.get('grafana', False)
    
    # GitHub configuration
    if extra_vars.get('project_config', {}).get('github'):
        extra_vars['github_org'] = extra_vars['project_config']['github'].get('organization', '')
    
    # Add environment variables if provided (these override config values)
    if env_vars:
        for key, value in env_vars.items():
            if value:  # Only add non-empty values
                extra_vars[key] = value
    
    return extra_vars


def build_ansible_command(ansible_dir, project_root, project_config, env_vars, tags=None, start_at_task=None):
    """
    Build complete Ansible playbook command with all necessary variables
    
    Args:
        ansible_dir (Path): Path to ansible directory
        project_root (Path): Root directory of superdeploy
        project_config (dict): Parsed project configuration
        env_vars (dict): Environment variables
        tags (str): Optional Ansible tags to run
        start_at_task (str): Optional task name to start from
    
    Returns:
        str: Complete ansible-playbook command
    """
    # Generate extra vars from project config
    extra_vars_dict = generate_ansible_extra_vars(project_config, env_vars, project_root)
    
    # Convert to JSON string for --extra-vars (with custom serializer for datetime)
    extra_vars_json = json.dumps(extra_vars_dict, default=json_serializer)
    # Escape single quotes for shell
    extra_vars_json = extra_vars_json.replace("'", "'\\''")
    
    # Build tags string
    tags_str = f"--tags {tags}" if tags else ""
    
    # Build start-at-task string
    start_at_str = f"--start-at-task='{start_at_task}'" if start_at_task else ""
    
    # Build the command
    cmd = f"""
cd {ansible_dir} && \\
SUPERDEPLOY_ROOT={project_root} ansible-playbook -i inventories/dev.ini playbooks/site.yml {tags_str} {start_at_str} \\
  --extra-vars '{extra_vars_json}'
"""
    
    return cmd.strip()
