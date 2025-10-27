"""SuperDeploy CLI - Ansible utility functions"""

import json
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
        extra_vars["addons_source_path"] = str(project_root / "addons")

        # Load project secrets from .env file
        project_name = extra_vars.get("project_name", "")
        if project_name:
            env_file = project_root / "projects" / project_name / ".env"
            if env_file.exists():
                from dotenv import dotenv_values

                project_secrets = dotenv_values(env_file)
                # Filter out non-secret values (comments, empty, etc.)
                extra_vars["project_secrets"] = {
                    k: v
                    for k, v in project_secrets.items()
                    if v and not k.startswith("#")
                }
            else:
                extra_vars["project_secrets"] = {}
        else:
            extra_vars["project_secrets"] = {}
    else:
        extra_vars["project_secrets"] = {}

    # Extract convenience vars from nested config
    network_config = extra_vars.get("network_config", {})
    if network_config:
        extra_vars["network_subnet"] = network_config.get(
            "docker_subnet", "172.30.0.0/24"
        )

    monitoring_config = extra_vars.get("monitoring", {})
    if monitoring_config:
        extra_vars["monitoring_enabled"] = monitoring_config.get("enabled", False)
        extra_vars["prometheus_enabled"] = monitoring_config.get("prometheus", False)
        extra_vars["grafana_enabled"] = monitoring_config.get("grafana", False)

    # GitHub configuration
    if extra_vars.get("project_config", {}).get("github"):
        extra_vars["github_org"] = extra_vars["project_config"]["github"].get(
            "organization", ""
        )

    # Add environment variables if provided (these override config values)
    if env_vars:
        for key, value in env_vars.items():
            if value:  # Only add non-empty values
                extra_vars[key] = value

    return extra_vars


def build_ansible_command(
    ansible_dir, project_root, project_config, env_vars, tags=None, project_name=None
):
    """
    Build complete Ansible playbook command with all necessary variables

    Args:
        ansible_dir (Path): Path to ansible directory
        project_root (Path): Root directory of superdeploy
        project_config (dict): Parsed project configuration
        env_vars (dict): Environment variables
        tags (str): Optional Ansible tags to run (e.g. 'foundation', 'addons', 'project')
        project_name (str): Project name for dynamic inventory file selection

    Returns:
        str: Complete ansible-playbook command
    """
    # Generate extra vars from project config
    extra_vars_dict = generate_ansible_extra_vars(
        project_config, env_vars, project_root
    )

    # Convert to JSON string for --extra-vars (with custom serializer for datetime)
    extra_vars_json = json.dumps(extra_vars_dict, default=json_serializer)
    # Escape single quotes for shell
    extra_vars_json = extra_vars_json.replace("'", "'\\''")

    # Build tags string
    tags_str = f"--tags {tags}" if tags else ""

    # Use project-specific inventory file if project_name is provided
    if not project_name:
        project_name = extra_vars_dict.get("project_name", "dev")
    inventory_file = f"inventories/{project_name}.ini"

    # Build the command
    cmd = f"""
cd {ansible_dir} && \\
SUPERDEPLOY_ROOT={project_root} ansible-playbook -i {inventory_file} playbooks/site.yml {tags_str} \\
  --extra-vars '{extra_vars_json}'
"""

    return cmd.strip()
