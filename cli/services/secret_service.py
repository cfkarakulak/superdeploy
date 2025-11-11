"""
Secret Management Service

Centralized secret loading, merging, and app-specific secret queries using domain models.
"""

from pathlib import Path
from typing import Dict, Optional

from cli.secret_manager import SecretManager
from cli.models.secrets import SecretConfig
from cli.constants import SENSITIVE_KEYWORDS


class SecretService:
    """
    Centralized secret management service with type-safe models.

    Responsibilities:
    - Load and cache secrets
    - Merge shared + app-specific secrets
    - Secret masking and display
    - Secret queries
    """

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize secret service.

        Args:
            project_root: Path to superdeploy root directory
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.secret_manager = SecretManager(project_root, project_name)
        self._secrets_cache: Optional[SecretConfig] = None

    def load_secrets(self, force_reload: bool = False) -> SecretConfig:
        """
        Load secret configuration with caching.

        Args:
            force_reload: Force reload from disk, ignore cache

        Returns:
            SecretConfig object
        """
        if self._secrets_cache is None or force_reload:
            self._secrets_cache = self.secret_manager.load_secrets()

        return self._secrets_cache

    def get_shared_secrets(self) -> Dict[str, str]:
        """
        Get shared secrets (available to all apps).

        Returns:
            Dictionary of shared secrets
        """
        config = self.load_secrets()
        return config.shared.values.copy()

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for app (shared + app-specific + aliases).

        Args:
            app_name: App name

        Returns:
            Dictionary of merged environment variables
        """
        config = self.load_secrets()
        return config.get_merged_secrets(app_name)

    def get_shared_secret(self, key: str) -> Optional[str]:
        """
        Get single shared secret value.

        Args:
            key: Secret key name

        Returns:
            Secret value or None if not found
        """
        config = self.load_secrets()
        return config.shared.get(key)

    def set_shared_secret(self, key: str, value: str) -> None:
        """
        Set a shared secret value and save to disk.

        Args:
            key: Secret key name
            value: Secret value
        """
        config = self.load_secrets()
        config.shared.set(key, value)
        self.secret_manager.save_secrets(config)
        self._secrets_cache = None  # Invalidate cache

    def set_app_secret(self, app_name: str, key: str, value: str) -> None:
        """
        Set an app-specific secret value and save to disk.

        Args:
            app_name: App name
            key: Secret key name
            value: Secret value
        """
        config = self.load_secrets()
        app_secrets = config.get_app_secrets(app_name)
        app_secrets.set(key, value)
        self.secret_manager.save_secrets(config)
        self._secrets_cache = None  # Invalidate cache

    def has_secrets(self) -> bool:
        """
        Check if secrets file exists.

        Returns:
            True if secrets file exists
        """
        return self.secret_manager.has_secrets()

    def mask_secret(self, value: str, show_chars: int = 4) -> str:
        """
        Mask secret value for safe display.

        Args:
            value: Secret value to mask
            show_chars: Number of characters to show at end

        Returns:
            Masked string (e.g., "***abcd")
        """
        if not value:
            return "***"

        if len(value) <= show_chars:
            return "***"

        return f"***{value[-show_chars:]}"

    def mask_secrets_in_dict(
        self, data: Dict[str, str], show_chars: int = 4
    ) -> Dict[str, str]:
        """
        Mask all sensitive secrets in a dictionary.

        Args:
            data: Dictionary with secret values
            show_chars: Number of characters to show at end

        Returns:
            Dictionary with masked sensitive values
        """
        masked = {}
        for key, value in data.items():
            if self.is_sensitive_key(key):
                masked[key] = self.mask_secret(value, show_chars)
            else:
                masked[key] = value
        return masked

    def is_sensitive_key(self, key: str) -> bool:
        """
        Check if key contains sensitive data (should be masked).

        Args:
            key: Secret key name

        Returns:
            True if key is sensitive
        """
        return any(keyword in key.upper() for keyword in SENSITIVE_KEYWORDS)

    def validate_required_secrets(self, required_keys: list[str]) -> list[str]:
        """
        Validate that required secrets exist and are not empty.

        Args:
            required_keys: List of required secret key names

        Returns:
            List of missing or empty keys
        """
        shared_secrets = self.get_shared_secrets()
        missing: list[str] = []

        for key in required_keys:
            value = shared_secrets.get(key, "").strip()
            if not value:
                missing.append(key)

        return missing

    def invalidate_cache(self) -> None:
        """Invalidate the secrets cache to force reload on next access."""
        self._secrets_cache = None
