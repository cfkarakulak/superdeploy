"""
Secret Management

Modern secret manager using domain models for type-safe secret handling.
"""

import yaml
from pathlib import Path
from typing import Dict

from cli.models.secrets import SecretConfig
from cli.exceptions import SecretError


class SecretFormatter:
    """Formats secret configuration for human-readable YAML output."""

    @staticmethod
    def format(config: SecretConfig) -> str:
        """
        Format secret configuration as human-readable YAML.

        Args:
            config: Secret configuration to format

        Returns:
            Formatted YAML string
        """
        lines = []

        # Header
        lines.append("# " + "=" * 77)
        lines.append(f"# {config.project_name.upper()} - Secrets Configuration")
        lines.append("# " + "=" * 77)
        lines.append("# WARNING: This file contains sensitive information")
        lines.append("# Keep this file secure and never commit to version control")
        lines.append("# " + "=" * 77)
        lines.append("")

        # Secrets section
        lines.append("# " + "=" * 77)
        lines.append("# Application Secrets")
        lines.append("# " + "=" * 77)
        lines.append("secrets:")

        # Shared secrets
        lines.append("")
        lines.append(
            "  # ---------------------------------------------------------------------------"
        )
        lines.append("  # Shared Secrets (available to all applications)")
        lines.append(
            "  # ---------------------------------------------------------------------------"
        )
        lines.append("  shared:")

        if config.shared.values:
            # Group by category for better readability
            db_keys = [k for k in config.shared.values if k.startswith("POSTGRES_")]
            mq_keys = [k for k in config.shared.values if k.startswith("RABBITMQ_")]
            docker_keys = [k for k in config.shared.values if k.startswith("DOCKER_")]
            other_keys = [
                k
                for k in config.shared.values
                if not any(
                    k.startswith(p) for p in ["POSTGRES_", "RABBITMQ_", "DOCKER_"]
                )
            ]

            if db_keys:
                lines.append("")
                lines.append("    # Database Configuration")
                for key in sorted(db_keys):
                    lines.append(f"    {key}: {config.shared.values[key]}")

            if mq_keys:
                lines.append("")
                lines.append("    # Message Queue Configuration")
                for key in sorted(mq_keys):
                    lines.append(f"    {key}: {config.shared.values[key]}")

            if docker_keys:
                lines.append("")
                lines.append("    # Docker Registry Configuration")
                for key in sorted(docker_keys):
                    lines.append(f"    {key}: {config.shared.values[key]}")

            if other_keys:
                lines.append("")
                lines.append("    # Other Shared Secrets")
                for key in sorted(other_keys):
                    lines.append(f"    {key}: {config.shared.values[key]}")
        else:
            lines.append("    {}")

        # App-specific secrets
        for app_name, app_secrets in config.apps.items():
            lines.append("")
            lines.append(
                "  # ---------------------------------------------------------------------------"
            )
            lines.append(f"  # {app_name.upper()} - Application-specific secrets")
            lines.append(
                "  # ---------------------------------------------------------------------------"
            )
            lines.append(f"  {app_name}:")
            if app_secrets.values:
                for key, value in sorted(app_secrets.values.items()):
                    lines.append(f"    {key}: {value}")
            else:
                lines.append("    # No app-specific secrets")

        # Environment aliases section
        if config.env_aliases:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Environment Variable Aliases")
            lines.append("# " + "=" * 77)
            lines.append(
                "# Maps addon environment variables to application-expected names"
            )
            lines.append(
                "# Example: DB_HOST: POSTGRES_HOST → DB_HOST gets value from POSTGRES_HOST"
            )
            lines.append("# " + "=" * 77)
            lines.append("env_aliases:")

            for app_name, aliases in config.env_aliases.items():
                lines.append("")
                lines.append(f"  {app_name}:")
                if aliases:
                    for alias_key, alias_value in sorted(aliases.items()):
                        lines.append(f"    {alias_key}: {alias_value}")
                else:
                    lines.append("    # No aliases needed")

        lines.append("")
        return "\n".join(lines)


class SecretManager:
    """
    Manages project secrets using type-safe domain models.

    Responsibilities:
    - Load/save secret configuration
    - Merge shared and app-specific secrets
    - Handle environment variable aliases
    - Maintain secret hierarchy
    """

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize secret manager.

        Args:
            project_root: Path to superdeploy root directory
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.secrets_file = project_root / "projects" / project_name / "secrets.yml"
        self.formatter = SecretFormatter()

    def load_secrets(self) -> SecretConfig:
        """
        Load secret configuration from file.

        Returns:
            SecretConfig object (empty if file doesn't exist)
        """
        if not self.secrets_file.exists():
            return SecretConfig(project_name=self.project_name)

        try:
            with open(self.secrets_file, "r") as f:
                data = yaml.safe_load(f) or {}
            return SecretConfig.from_dict(self.project_name, data)
        except Exception as e:
            raise SecretError(
                "Failed to load secrets file",
                context=f"File: {self.secrets_file}, Error: {str(e)}",
            )

    def save_secrets(self, config: SecretConfig) -> None:
        """
        Save secret configuration to file.

        Args:
            config: Secret configuration to save
        """
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        formatted_content = self.formatter.format(config)

        try:
            with open(self.secrets_file, "w") as f:
                f.write(formatted_content)
            # Set restrictive permissions
            self.secrets_file.chmod(0o600)
        except Exception as e:
            raise SecretError(
                "Failed to save secrets file",
                context=f"File: {self.secrets_file}, Error: {str(e)}",
            )

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for specific app.

        Merges:
        - secrets.shared (all apps)
        - secrets.{app_name} (app-specific)
        - env_aliases.{app_name} (variable name mappings)

        Args:
            app_name: Name of the application

        Returns:
            Dictionary of environment variables for the app
        """
        config = self.load_secrets()
        return config.get_merged_secrets(app_name)

    def get_shared_secrets(self) -> Dict[str, str]:
        """
        Get shared secrets available to all apps.

        Returns:
            Dictionary of shared environment variables
        """
        config = self.load_secrets()
        return config.shared.values.copy()

    def set_shared_secret(self, key: str, value: str) -> None:
        """
        Set a shared secret value.

        Args:
            key: Secret key name
            value: Secret value
        """
        config = self.load_secrets()
        config.shared.set(key, value)
        self.save_secrets(config)

    def set_app_secret(self, app_name: str, key: str, value: str) -> None:
        """
        Set an app-specific secret value.

        Args:
            app_name: Name of the application
            key: Secret key name
            value: Secret value
        """
        config = self.load_secrets()
        app_secrets = config.get_app_secrets(app_name)
        app_secrets.set(key, value)
        self.save_secrets(config)

    def has_secrets(self) -> bool:
        """
        Check if secrets file exists.

        Returns:
            True if secrets file exists
        """
        return self.secrets_file.exists()
