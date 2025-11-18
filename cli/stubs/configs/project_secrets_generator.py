"""
Generates project secrets for database storage.
Replaces secrets.yml file-based approach with database-backed secrets.
"""

import secrets
import string
from typing import Dict, List


def generate_password(length: int = 32) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_project_secrets(
    project_name: str, app_names: List[str], addons: Dict
) -> str:
    """
    Generate secrets for project in YAML format.
    
    Args:
        project_name: Name of the project
        app_names: List of application names
        addons: Dictionary of addon configurations (category -> instance -> config)
        
    Returns:
        YAML string containing secrets structure
    """
    secrets_data = {
        "secrets": {
            "shared": {},
            "addons": {},
            "apps": {},
        }
    }

    # 1. Generate shared secrets (placeholders - user must fill in)
    secrets_data["secrets"]["shared"] = {
        "DOCKER_ORG": "CHANGE_ME",
        "DOCKER_USERNAME": "CHANGE_ME",
        "DOCKER_TOKEN": "CHANGE_ME",
        "REPOSITORY_TOKEN": "CHANGE_ME",
        # SMTP is optional
        "SMTP_HOST": "",
        "SMTP_PORT": "587",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
    }

    # 2. Generate addon secrets based on configuration
    if addons:
        # Databases
        if "databases" in addons:
            for instance_name, config in addons["databases"].items():
                addon_type = config.get("type")
                
                if addon_type == "postgres":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",  # Ansible sets this from VM IP
                        "PORT": "5432",
                        "USER": f"{project_name}_user",
                        "PASSWORD": generate_password(),
                        "DATABASE": f"{project_name}_db",
                    }
                
                elif addon_type == "mysql":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",
                        "PORT": "3306",
                        "USER": f"{project_name}_user",
                        "PASSWORD": generate_password(),
                        "DATABASE": f"{project_name}_db",
                    }
                
                elif addon_type == "mongodb":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",
                        "PORT": "27017",
                        "USER": f"{project_name}_user",
                        "PASSWORD": generate_password(),
                        "DATABASE": f"{project_name}_db",
                    }

        # Queues
        if "queues" in addons:
            for instance_name, config in addons["queues"].items():
                addon_type = config.get("type")
                
                if addon_type == "rabbitmq":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",
                        "PORT": "5672",
                        "MANAGEMENT_PORT": "15672",
                        "USER": f"{project_name}_user",
                        "PASSWORD": generate_password(),
                    }

        # Caches
        if "caches" in addons:
            for instance_name, config in addons["caches"].items():
                addon_type = config.get("type")
                
                if addon_type == "redis":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",
                        "PORT": "6379",
                        "PASSWORD": generate_password(),
                    }
                
                elif addon_type == "memcached":
                    if addon_type not in secrets_data["secrets"]["addons"]:
                        secrets_data["secrets"]["addons"][addon_type] = {}
                    
                    secrets_data["secrets"]["addons"][addon_type][instance_name] = {
                        "HOST": "WILL_BE_SET_BY_ANSIBLE",
                        "PORT": "11211",
                    }

    # 3. Generate app-specific secrets (empty by default - user can add)
    for app_name in app_names:
        secrets_data["secrets"]["apps"][app_name] = {}

    # Convert to YAML string
    import yaml
    return yaml.dump(secrets_data, default_flow_style=False, sort_keys=False)

