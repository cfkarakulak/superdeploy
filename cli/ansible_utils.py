"""SuperDeploy CLI - Ansible utility functions"""

import json
import yaml
from pathlib import Path
from rich.console import Console

console = Console()


def parse_project_config(project, project_root):
    """
    Parse project.yml and extract configuration for deployment
    
    Args:
        project (str): Project name
        project_root (Path): Root directory of superdeploy
    
    Returns:
        dict: Parsed project configuration with enabled_addons, addon_configs, apps, etc.
    """
    project_dir = project_root / "projects" / project
    config_file = project_dir / "project.yml"
    
    if not config_file.exists():
        console.print(f"[red]❌ Config not found: {config_file}[/red]")
        console.print(f"[dim]Run: superdeploy init -p {project}[/dim]")
        raise SystemExit(1)
    
    with open(config_file) as f:
        raw_config = yaml.safe_load(f)
    
    # Extract enabled addons from both infrastructure and core_services
    enabled_addons = []
    enabled_addons.extend(list(raw_config.get('infrastructure', {}).keys()))
    enabled_addons.extend(list(raw_config.get('core_services', {}).keys()))
    
    # Extract addon configurations from both sections
    addon_configs = {}
    for addon_name, addon_config in raw_config.get('infrastructure', {}).items():
        addon_configs[addon_name] = addon_config if isinstance(addon_config, dict) else {}
    for addon_name, addon_config in raw_config.get('core_services', {}).items():
        addon_configs[addon_name] = addon_config if isinstance(addon_config, dict) else {}
    
    # Extract app configurations
    apps = raw_config.get('apps', {})
    
    # Return both raw config and parsed values
    return {
        # Parsed values for easy access
        'project_name': raw_config.get('project', project),
        'enabled_addons': enabled_addons,
        'addon_configs': addon_configs,
        'apps': apps,
        'network': raw_config.get('network', {}),
        'monitoring': raw_config.get('monitoring', {}),
        'github': raw_config.get('github', {}),
        'domain': raw_config.get('domain', ''),
        'vms': raw_config.get('vms', {}),
        'infrastructure': raw_config.get('infrastructure', {}),
        # Full raw config for Ansible
        '_raw': raw_config,
    }


def generate_ansible_extra_vars(project_config, env_vars=None, project_root=None):
    """
    Generate Ansible extra vars from project configuration
    
    Args:
        project_config (dict): Parsed project configuration
        env_vars (dict): Optional environment variables to include
        project_root (Path): Root directory of superdeploy
    
    Returns:
        dict: Dictionary of extra vars for Ansible
    """
    extra_vars = {}
    
    # Pass the raw project config (needed by addon-deployer role)
    if '_raw' in project_config:
        # Convert datetime objects to strings for JSON serialization
        raw_config = project_config['_raw'].copy()
        if 'created_at' in raw_config and hasattr(raw_config['created_at'], 'isoformat'):
            raw_config['created_at'] = raw_config['created_at'].isoformat()
        extra_vars['project_config'] = raw_config
    else:
        # Fallback: construct from available fields
        full_config = {k: v for k, v in project_config.items() 
                       if k not in ['enabled_addons', 'addon_configs', '_raw']}
        extra_vars['project_config'] = full_config
    
    # Project name
    extra_vars['project_name'] = project_config['project_name']
    
    # Enabled addons as list (not JSON string)
    extra_vars['enabled_addons'] = project_config['enabled_addons']
    
    # Addon configurations as dict (not JSON string)
    extra_vars['addon_configs'] = project_config['addon_configs']
    
    # Apps configuration as dict (not JSON string)
    extra_vars['apps'] = project_config['apps']
    
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
    
    # Network configuration
    if project_config.get('network'):
        extra_vars['network_subnet'] = project_config['network'].get('subnet', '172.20.0.0/24')
    
    # Monitoring configuration
    if project_config.get('monitoring'):
        extra_vars['monitoring_enabled'] = project_config['monitoring'].get('enabled', False)
        extra_vars['prometheus_enabled'] = project_config['monitoring'].get('prometheus', False)
        extra_vars['grafana_enabled'] = project_config['monitoring'].get('grafana', False)
    
    # Domain configuration
    if project_config.get('domain'):
        extra_vars['project_domain'] = project_config['domain']
    
    # GitHub configuration
    if project_config.get('github'):
        extra_vars['github_org'] = project_config['github'].get('organization', '')
    
    # Add environment variables if provided
    if env_vars:
        for key, value in env_vars.items():
            if value:  # Only add non-empty values
                extra_vars[key] = value
    
    return extra_vars


def build_ansible_command(ansible_dir, project_root, project_config, env_vars, tags=None):
    """
    Build complete Ansible playbook command with all necessary variables
    
    Args:
        ansible_dir (Path): Path to ansible directory
        project_root (Path): Root directory of superdeploy
        project_config (dict): Parsed project configuration
        env_vars (dict): Environment variables
        tags (str): Optional Ansible tags to run
    
    Returns:
        str: Complete ansible-playbook command
    """
    # Generate extra vars from project config
    extra_vars_dict = generate_ansible_extra_vars(project_config, env_vars, project_root)
    
    # Convert to JSON string for --extra-vars
    extra_vars_json = json.dumps(extra_vars_dict)
    # Escape single quotes for shell
    extra_vars_json = extra_vars_json.replace("'", "'\\''")
    
    # Build tags string
    tags_str = f"--tags {tags}" if tags else ""
    
    # Build the command
    cmd = f"""
cd {ansible_dir} && \\
SUPERDEPLOY_ROOT={project_root} ansible-playbook -i inventories/dev.ini playbooks/site.yml {tags_str} \\
  --extra-vars '{extra_vars_json}'
"""
    
    return cmd.strip()
