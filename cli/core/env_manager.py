"""
EnvManager - Centralized environment variable management

Handles:
- Addon-provided variables (POSTGRES_*, RABBITMQ_*, etc.)
- App-specific aliases (DB_*, NEXT_PUBLIC_*, etc.)
- Static values and clones from other variables
- No more hardcoded mappings in sync.py or generate.py!

Example project.yml:
    apps:
      api:
        env_aliases:
          DB_HOST: POSTGRES_HOST      # Clone from addon variable
          DB_CONNECTION: "app"         # Static value
"""

from typing import Dict, Any
from pathlib import Path
import yaml


class EnvManager:
    """
    Centralized environment variable management system.

    Resolves env_aliases from project config:
    - Static values: DB_CONNECTION: "app"
    - Clones: DB_HOST: POSTGRES_HOST
    """

    def __init__(self, project_config: Dict[str, Any]):
        """
        Initialize EnvManager with project configuration.

        Args:
            project_config: Loaded project.yml as dict
        """
        self.project_config = project_config
        self.project_name = project_config.get("project", {}).get("name", "unknown")

    def resolve_aliases(
        self, app_name: str, base_env: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Resolve env_aliases for a specific app.

        Args:
            app_name: Name of the app (e.g., "api", "storefront")
            base_env: Base environment variables (from addons)

        Returns:
            Dict with resolved aliases merged into base_env

        Example:
            base_env = {"POSTGRES_HOST": "10.1.0.2", "POSTGRES_PORT": "5432"}
            app_name = "api"

            Result:
            {
                "POSTGRES_HOST": "10.1.0.2",
                "POSTGRES_PORT": "5432",
                "DB_HOST": "10.1.0.2",        # Cloned from POSTGRES_HOST
                "DB_PORT": "5432",             # Cloned from POSTGRES_PORT
                "DB_CONNECTION": "app"         # Static value
            }
        """
        # Get app config
        apps = self.project_config.get("apps", {})
        app_config = apps.get(app_name)

        if not app_config:
            # No app config found, return base_env unchanged
            return base_env.copy()

        # Get env_aliases for this app
        env_aliases = app_config.get("env_aliases", {})

        if not env_aliases:
            # No aliases defined, return base_env unchanged
            return base_env.copy()

        # Start with base environment
        resolved = base_env.copy()

        # Resolve each alias
        for alias_name, alias_value in env_aliases.items():
            if isinstance(alias_value, str):
                # Check if it's a static value (quoted string) or a clone
                if alias_value.startswith('"') and alias_value.endswith('"'):
                    # Static value (remove quotes)
                    resolved[alias_name] = alias_value[1:-1]
                elif alias_value in base_env:
                    # Clone from another variable
                    resolved[alias_name] = base_env[alias_value]
                else:
                    # Assume it's a reference to another variable
                    # If the source doesn't exist in base_env, treat as static
                    resolved[alias_name] = alias_value
            else:
                # Non-string value (int, bool, etc.) - convert to string
                resolved[alias_name] = str(alias_value)

        return resolved

    def get_app_env_secrets(
        self, app_name: str, addon_secrets: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Get complete environment secrets for an app (addon + aliases).

        This replaces hardcoded mapping in sync.py:
            OLD: if "POSTGRES_HOST" in env: secrets["DB_HOST"] = env["POSTGRES_HOST"]
            NEW: secrets = env_manager.get_app_env_secrets("api", env)

        Args:
            app_name: Name of the app
            addon_secrets: Secrets from addons (POSTGRES_*, RABBITMQ_*, etc.)

        Returns:
            Complete secrets dict with resolved aliases
        """
        return self.resolve_aliases(app_name, addon_secrets)

    def get_alias_keys(self, app_name: str) -> list[str]:
        """
        Get list of alias keys for an app.

        Useful for adding aliases to github_secrets/forgejo_secrets lists.

        Args:
            app_name: Name of the app

        Returns:
            List of alias key names (e.g., ["DB_HOST", "DB_PORT", ...])
        """
        apps = self.project_config.get("apps", {})
        app_config = apps.get(app_name)

        if not app_config:
            return []

        env_aliases = app_config.get("env_aliases", {})
        return list(env_aliases.keys())

    @staticmethod
    def from_project_file(project_file: Path) -> "EnvManager":
        """
        Create EnvManager from project.yml file.

        Args:
            project_file: Path to project.yml

        Returns:
            EnvManager instance
        """
        with open(project_file, "r") as f:
            project_config = yaml.safe_load(f)

        return EnvManager(project_config)
