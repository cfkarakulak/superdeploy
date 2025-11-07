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
