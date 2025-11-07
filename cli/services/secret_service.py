"""
Secret Management Service

Centralized secret loading, merging, and app-specific secret queries.
Used by 10+ commands that need secret access.
"""

from pathlib import Path
from typing import Dict, Optional, Any
from cli.secret_manager import SecretManager
from cli.constants import SENSITIVE_KEYWORDS, SECRET_FILE_PERMISSIONS


class SecretService:
    """
    Centralized secret management service.

    Responsibilities:
    - Load and cache secrets
    - Merge shared + app-specific secrets
    - Secret queries
    """

    def __init__(self, project_root: Path, project_name: str):
        self.project_root = project_root
        self.project_name = project_name
        self.secret_manager = SecretManager(project_root, project_name)
        self._secrets_cache: Optional[Dict[str, Any]] = None

    def load_secrets(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load secrets with caching.

        Args:
            force_reload: Force reload from disk

        Returns:
            Full secrets structure with shared and app-specific sections
        """
        if self._secrets_cache is None or force_reload:
            self._secrets_cache = self.secret_manager.load_secrets()

        return self._secrets_cache

    def get_shared_secrets(self) -> Dict[str, Any]:
        """
        Get shared secrets (available to all apps).

        Returns:
            Shared secrets dictionary
        """
        secrets = self.load_secrets()
        return secrets.get("secrets", {}).get("shared", {})

    def get_app_secrets(self, app_name: str) -> Dict[str, Any]:
        """
        Get merged secrets for app (shared + app-specific).

        Args:
            app_name: App name

        Returns:
            Merged secrets dictionary
        """
        return self.secret_manager.get_app_secrets(app_name)

    def mask_secret(self, value: str, show_chars: int = 4) -> str:
        """
        Mask secret value for display.

        Args:
            value: Secret value
            show_chars: Number of chars to show at end

        Returns:
            Masked string (e.g., "***abcd")
        """
        if not value:
            return "***"

        if len(value) <= show_chars:
            return "***"

        return f"***{value[-show_chars:]}"

    def is_sensitive_key(self, key: str) -> bool:
        """
        Check if key is sensitive (should be masked).

        Args:
            key: Secret key name

        Returns:
            True if sensitive
        """
        return any(keyword in key.upper() for keyword in SENSITIVE_KEYWORDS)

    def save_secrets(self, secrets_data: Dict[str, Any]) -> None:
        """
        Save secrets to disk.

        Args:
            secrets_data: Complete secrets structure
        """
        self.secret_manager.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        import yaml

        with open(self.secret_manager.secrets_file, "w") as f:
            yaml.dump(secrets_data, f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions from constants
        self.secret_manager.secrets_file.chmod(SECRET_FILE_PERMISSIONS)

        self._secrets_cache = None  # Invalidate cache
