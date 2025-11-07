"""Secret management with hierarchy support"""

import yaml
from pathlib import Path
from typing import Dict, Any


class SecretManager:
    """Manages secrets with shared + app-specific hierarchy"""

    def __init__(self, project_root: Path, project_name: str):
        self.project_root = project_root
        self.project_name = project_name
        self.secrets_file = project_root / "projects" / project_name / "secrets.yml"

    def load_secrets(self) -> Dict[str, Any]:
        """Load secrets.yml"""
        if not self.secrets_file.exists():
            return {}

        with open(self.secrets_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_secrets(self, secrets: Dict[str, Any]):
        """Save secrets to secrets.yml"""
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.secrets_file, "w") as f:
            yaml.dump(secrets, f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions
        self.secrets_file.chmod(0o600)

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for specific app

        Merges:
        - secrets.shared (all apps)
        - secrets.{app_name} (app-specific)

        Returns:
            Dict of environment variables for the app
        """
        all_secrets = self.load_secrets()

        # Get structure
        secrets_section = all_secrets.get("secrets", {})

        # Merge shared + app-specific
        merged = {}

        # 1. Add shared secrets
        shared = secrets_section.get("shared", {})
        if shared:
            merged.update(shared)

        # 2. Add app-specific secrets (overrides shared if duplicate)
        app_specific = secrets_section.get(app_name, {})
        if app_specific:
            merged.update(app_specific)

        return merged

    def get_all_app_secrets(self, app_names: list) -> Dict[str, Dict[str, str]]:
        """Get secrets for all apps"""
        result = {}
        for app_name in app_names:
            result[app_name] = self.get_app_secrets(app_name)
        return result

    def add_shared_secret(self, key: str, value: str):
        """Add secret to shared section"""
        secrets = self.load_secrets()

        if "secrets" not in secrets:
            secrets["secrets"] = {}

        if "shared" not in secrets["secrets"]:
            secrets["secrets"]["shared"] = {}

        secrets["secrets"]["shared"][key] = value
        self.save_secrets(secrets)

    def add_app_secret(self, app_name: str, key: str, value: str):
        """Add secret to app-specific section"""
        secrets = self.load_secrets()

        if "secrets" not in secrets:
            secrets["secrets"] = {}

        if app_name not in secrets["secrets"]:
            secrets["secrets"][app_name] = {}

        secrets["secrets"][app_name][key] = value
        self.save_secrets(secrets)

    def initialize_from_addons(self, addons: Dict[str, Any], project_name: str):
        """Initialize secrets.yml from addon passwords"""
        import secrets as py_secrets

        shared_secrets = {}

        for addon_name, addon_config in addons.items():
            # Get env vars from addon
            env_vars = (
                addon_config.env_vars if hasattr(addon_config, "env_vars") else {}
            )

            for var_name, var_config in env_vars.items():
                # Generate secure password
                if isinstance(var_config, dict):
                    if var_config.get("type") == "password":
                        password = py_secrets.token_urlsafe(32)
                        shared_secrets[var_name] = password
                    elif var_config.get("type") == "username":
                        shared_secrets[var_name] = f"{project_name}_user"
                    elif var_config.get("type") == "database":
                        shared_secrets[var_name] = f"{project_name}_db"
                    elif "default" in var_config:
                        shared_secrets[var_name] = var_config["default"]

        # Create structure
        secrets = {"secrets": {"shared": shared_secrets}}

        self.save_secrets(secrets)

        return shared_secrets
