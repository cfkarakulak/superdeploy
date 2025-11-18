"""Configuration and secrets management service."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import secrets
import string


class ConfigService:
    """Service for managing config.yml and database secrets."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def get_project_dir(self, project_name: str) -> Path:
        """Get project directory path."""
        return self.project_root / "projects" / project_name

    def read_config(self, project_name: str) -> Dict[str, Any]:
        """
        Read config.yml for a project.

        Args:
            project_name: Name of the project

        Returns:
            Configuration dictionary
        """
        config_file = self.get_project_dir(project_name) / "config.yml"

        if not config_file.exists():
            raise FileNotFoundError(f"config.yml not found for project {project_name}")

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise Exception(f"Failed to read config.yml: {str(e)}")

    def write_config(self, project_name: str, config: Dict[str, Any]) -> None:
        """
        Write config.yml for a project.

        Args:
            project_name: Name of the project
            config: Configuration dictionary
        """
        config_file = self.get_project_dir(project_name) / "config.yml"

        try:
            with open(config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise Exception(f"Failed to write config.yml: {str(e)}")

    def read_secrets(self, project_name: str) -> Dict[str, Any]:
        """
        Read secrets from database for a project (legacy compatibility method).

        Args:
            project_name: Name of the project

        Returns:
            Secrets dictionary in legacy format
        """
        from database import SessionLocal
        from models import Secret

        db = SessionLocal()
        try:
            secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == project_name,
                    Secret.environment == "production",
                )
                .all()
            )

            if not secrets:
                raise FileNotFoundError(f"No secrets found for project {project_name}")

            # Build legacy format
            result = {"secrets": {"shared": {}, "apps": {}, "addons": {}}}

            for secret in secrets:
                if secret.app_name is None:
                    if secret.source == "addon":
                        result["secrets"]["addons"][secret.key] = secret.value
                    else:
                        result["secrets"]["shared"][secret.key] = secret.value
                else:
                    if secret.app_name not in result["secrets"]["apps"]:
                        result["secrets"]["apps"][secret.app_name] = {}
                    result["secrets"]["apps"][secret.app_name][secret.key] = (
                        secret.value
                    )

            return result
        finally:
            db.close()

    def write_secrets(self, project_name: str, secrets_data: Dict[str, Any]) -> None:
        """
        Write secrets to database for a project (legacy compatibility method).

        Args:
            project_name: Name of the project
            secrets_data: Secrets dictionary in legacy format
        """
        from database import SessionLocal

        db = SessionLocal()
        try:
            # This method is for legacy compatibility
            # Modern code should use Secret model directly
            raise NotImplementedError(
                "write_secrets is deprecated. Use Secret model directly for database operations."
            )
        finally:
            db.close()

    def get_app_secrets(self, project_name: str, app_name: str) -> Dict[str, str]:
        """
        Get secrets for a specific app (includes shared secrets).

        Args:
            project_name: Name of the project
            app_name: Name of the app

        Returns:
            Dictionary of secret key-value pairs
        """
        secrets_data = self.read_secrets(project_name)

        # Start with shared secrets
        all_secrets = secrets_data.get("secrets", {}).get("shared", {}).copy()

        # Override with app-specific secrets
        app_secrets = secrets_data.get("secrets", {}).get(app_name, {})
        all_secrets.update(app_secrets)

        return all_secrets

    def set_app_secret(
        self, project_name: str, app_name: str, key: str, value: str
    ) -> None:
        """
        Set a secret for a specific app.

        Args:
            project_name: Name of the project
            app_name: Name of the app
            key: Secret key
            value: Secret value
        """
        secrets_data = self.read_secrets(project_name)

        # Ensure structure exists
        if "secrets" not in secrets_data:
            secrets_data["secrets"] = {}

        if app_name == "shared":
            if "shared" not in secrets_data["secrets"]:
                secrets_data["secrets"]["shared"] = {}
            secrets_data["secrets"]["shared"][key] = value
        else:
            if app_name not in secrets_data["secrets"]:
                secrets_data["secrets"][app_name] = {}
            secrets_data["secrets"][app_name][key] = value

        self.write_secrets(project_name, secrets_data)

    def delete_app_secret(self, project_name: str, app_name: str, key: str) -> None:
        """
        Delete a secret for a specific app.

        Args:
            project_name: Name of the project
            app_name: Name of the app
            key: Secret key to delete
        """
        secrets_data = self.read_secrets(project_name)

        if app_name == "shared":
            if "shared" in secrets_data.get("secrets", {}):
                secrets_data["secrets"]["shared"].pop(key, None)
        else:
            if app_name in secrets_data.get("secrets", {}):
                secrets_data["secrets"][app_name].pop(key, None)

        self.write_secrets(project_name, secrets_data)

    def get_addon_vars(self, project_name: str, app_name: str) -> Dict[str, str]:
        """
        Get addon-generated environment variables for an app.

        These are read-only variables generated from addon attachments.

        Args:
            project_name: Name of the project
            app_name: Name of the app

        Returns:
            Dictionary of addon-generated env vars
        """
        config = self.read_config(project_name)
        secrets_data = self.read_secrets(project_name)

        addon_vars = {}

        # Find app in config
        apps = config.get("apps", {})
        app_config = apps.get(app_name)

        if not app_config:
            return addon_vars

        # Get addon attachments
        attachments = app_config.get("addons", [])

        for attachment in attachments:
            # Parse attachment (can be string or dict)
            if isinstance(attachment, str):
                # Simple format: "databases.primary"
                addon_ref = attachment
                as_prefix = self._get_default_prefix(addon_ref)
            else:
                # Full format with 'as'
                addon_ref = attachment.get("addon")
                as_prefix = attachment.get("as", self._get_default_prefix(addon_ref))

            # Get addon credentials from secrets
            addon_category, addon_name = addon_ref.split(".")
            addon_type = self._get_addon_type(config, addon_category, addon_name)

            if addon_type:
                addon_secrets = (
                    secrets_data.get("addons", {})
                    .get(addon_type, {})
                    .get(addon_name, {})
                )

                # Generate env vars based on addon type
                if addon_type == "postgres":
                    addon_vars[f"{as_prefix}_URL"] = self._generate_postgres_url(
                        addon_secrets
                    )
                    addon_vars[f"{as_prefix}_HOST"] = addon_secrets.get("HOST", "")
                    addon_vars[f"{as_prefix}_PORT"] = str(addon_secrets.get("PORT", ""))
                    addon_vars[f"{as_prefix}_USER"] = addon_secrets.get("USER", "")
                    addon_vars[f"{as_prefix}_PASSWORD"] = addon_secrets.get(
                        "PASSWORD", ""
                    )
                    addon_vars[f"{as_prefix}_DATABASE"] = addon_secrets.get(
                        "DATABASE", ""
                    )

                elif addon_type == "redis":
                    addon_vars[f"{as_prefix}_URL"] = self._generate_redis_url(
                        addon_secrets
                    )
                    addon_vars[f"{as_prefix}_HOST"] = addon_secrets.get("HOST", "")
                    addon_vars[f"{as_prefix}_PORT"] = str(addon_secrets.get("PORT", ""))
                    addon_vars[f"{as_prefix}_PASSWORD"] = addon_secrets.get(
                        "PASSWORD", ""
                    )

                elif addon_type == "rabbitmq":
                    addon_vars[f"{as_prefix}_URL"] = self._generate_rabbitmq_url(
                        addon_secrets
                    )
                    addon_vars[f"{as_prefix}_HOST"] = addon_secrets.get("HOST", "")
                    addon_vars[f"{as_prefix}_PORT"] = str(addon_secrets.get("PORT", ""))
                    addon_vars[f"{as_prefix}_USER"] = addon_secrets.get("USER", "")
                    addon_vars[f"{as_prefix}_PASSWORD"] = addon_secrets.get(
                        "PASSWORD", ""
                    )
                    addon_vars[f"{as_prefix}_VHOST"] = addon_secrets.get("VHOST", "/")

        return addon_vars

    def _get_default_prefix(self, addon_ref: str) -> str:
        """Get default env var prefix for addon reference."""
        category = addon_ref.split(".")[0]

        prefix_map = {
            "databases": "DATABASE",
            "caches": "CACHE",
            "queues": "QUEUE",
            "search": "SEARCH",
            "proxy": "PROXY",
        }

        return prefix_map.get(category, category.upper())

    def _get_addon_type(self, config: Dict, category: str, name: str) -> Optional[str]:
        """Get addon type from config."""
        addons = config.get("addons", {})
        category_addons = addons.get(category, {})
        addon_config = category_addons.get(name, {})
        return addon_config.get("type")

    def _generate_postgres_url(self, credentials: Dict) -> str:
        """Generate PostgreSQL connection URL."""
        user = credentials.get("USER", "")
        password = credentials.get("PASSWORD", "")
        host = credentials.get("HOST", "")
        port = credentials.get("PORT", "5432")
        database = credentials.get("DATABASE", "")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def _generate_redis_url(self, credentials: Dict) -> str:
        """Generate Redis connection URL."""
        host = credentials.get("HOST", "")
        port = credentials.get("PORT", "6379")
        password = credentials.get("PASSWORD", "")

        if password:
            return f"redis://default:{password}@{host}:{port}"
        return f"redis://{host}:{port}"

    def _generate_rabbitmq_url(self, credentials: Dict) -> str:
        """Generate RabbitMQ connection URL."""
        user = credentials.get("USER", "")
        password = credentials.get("PASSWORD", "")
        host = credentials.get("HOST", "")
        port = credentials.get("PORT", "5672")
        vhost = credentials.get("VHOST", "/")

        return f"amqp://{user}:{password}@{host}:{port}{vhost}"

    def generate_secure_password(self, length: int = 32) -> str:
        """
        Generate a secure random password.

        Args:
            length: Length of the password

        Returns:
            Secure random password string
        """
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate configuration structure.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation
        if "project" not in config:
            return False, "Missing 'project' field"

        if "apps" not in config:
            return False, "Missing 'apps' section"

        # Validate apps
        apps = config.get("apps", {})
        for app_name, app_config in apps.items():
            if not isinstance(app_config, dict):
                return False, f"Invalid app config for {app_name}"

            if "vm" not in app_config:
                return False, f"Missing 'vm' field for app {app_name}"

        return True, None
