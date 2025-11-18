"""
Secret Management

Database-backed secret manager.
All secrets are stored in PostgreSQL.
"""

from pathlib import Path
from typing import Dict, Optional
from cli.database import get_db_session, Secret, SecretAlias
from sqlalchemy.orm import Session


class SecretManager:
    """
    Database-backed secret manager.

    All operations work with PostgreSQL database.
    """

    def __init__(
        self, project_root: Path, project_name: str, environment: str = "production"
    ):
        """
        Initialize secret manager.

        Args:
            project_root: Path to superdeploy root directory (kept for compatibility)
            project_name: Name of the project
            environment: Environment (production/staging)
        """
        self.project_root = project_root
        self.project_name = project_name
        self.environment = environment

    def _get_db(self) -> Session:
        """Get database session."""
        return get_db_session()

    def _resolve_alias(self, alias_value: str, db: Session) -> Optional[str]:
        """
        Resolve an alias value like 'postgres.primary.HOST' to actual value.

        Args:
            alias_value: Alias target key (e.g. postgres.primary.HOST)
            db: Database session

        Returns:
            Resolved value or None if not found
        """
        # Alias format: addon_type.instance_name.KEY
        # e.g. postgres.primary.HOST
        parts = alias_value.split(".")
        if len(parts) < 3:
            return None

        # The alias points to an addon secret key
        # postgres.primary.HOST is stored as key in secrets table
        secret = (
            db.query(Secret)
            .filter(
                Secret.project_name == self.project_name,
                Secret.key == alias_value,
                Secret.environment == self.environment,
            )
            .first()
        )

        return secret.value if secret else None

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for specific app with alias resolution.

        Merges:
        - Shared secrets (app_name=NULL)
        - Addon secrets (source='addon')
        - App-specific secrets (app_name={app})
        - Resolves aliases

        Args:
            app_name: Name of the application

        Returns:
            Dictionary of environment variables for the app
        """
        db = self._get_db()
        try:
            merged = {}

            # 1. Get shared secrets (app_name=NULL)
            shared_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.app_name.is_(None),
                    Secret.environment == self.environment,
                )
                .all()
            )

            for secret in shared_secrets:
                merged[secret.key] = secret.value

            # 2. Get app-specific secrets
            app_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.app_name == app_name,
                    Secret.environment == self.environment,
                )
                .all()
            )

            for secret in app_secrets:
                merged[secret.key] = secret.value  # Override shared

            # 3. Apply aliases
            aliases = (
                db.query(SecretAlias)
                .filter(
                    SecretAlias.project_name == self.project_name,
                    SecretAlias.app_name == app_name,
                )
                .all()
            )

            for alias in aliases:
                # Resolve alias to actual value
                resolved_value = self._resolve_alias(alias.target_key, db)
                if resolved_value:
                    merged[alias.alias_key] = resolved_value

            return merged

        finally:
            db.close()

    def get_shared_secrets(self) -> Dict[str, str]:
        """
        Get shared secrets available to all apps.

        Returns:
            Dictionary of shared environment variables
        """
        db = self._get_db()
        try:
            secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.app_name.is_(None),
                    Secret.environment == self.environment,
                )
                .all()
            )

            return {s.key: s.value for s in secrets}
        finally:
            db.close()

    def set_shared_secret(self, key: str, value: str) -> None:
        """
        Set a shared secret value.

        Args:
            key: Secret key name
            value: Secret value
        """
        db = self._get_db()
        try:
            # Upsert (update or insert)
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.app_name.is_(None),
                    Secret.key == key,
                    Secret.environment == self.environment,
                )
                .first()
            )

            if secret:
                secret.value = value
            else:
                secret = Secret(
                    project_name=self.project_name,
                    app_name=None,
                    key=key,
                    value=value,
                    environment=self.environment,
                    source="shared",
                    editable=True,
                )
                db.add(secret)

            db.commit()
        finally:
            db.close()

    def set_app_secret(self, app_name: str, key: str, value: str) -> None:
        """
        Set an app-specific secret value.

        Args:
            app_name: Name of the application
            key: Secret key name
            value: Secret value
        """
        db = self._get_db()
        try:
            # Upsert (update or insert)
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.app_name == app_name,
                    Secret.key == key,
                    Secret.environment == self.environment,
                )
                .first()
            )

            if secret:
                secret.value = value
            else:
                secret = Secret(
                    project_name=self.project_name,
                    app_name=app_name,
                    key=key,
                    value=value,
                    environment=self.environment,
                    source="app",
                    editable=True,
                )
                db.add(secret)

            db.commit()
        finally:
            db.close()

    def delete_secret(self, app_name: Optional[str], key: str) -> bool:
        """
        Delete a secret.

        Args:
            app_name: Name of the application (None for shared)
            key: Secret key name

        Returns:
            True if deleted, False if not found
        """
        db = self._get_db()
        try:
            query = db.query(Secret).filter(
                Secret.project_name == self.project_name,
                Secret.key == key,
                Secret.environment == self.environment,
            )

            if app_name:
                query = query.filter(Secret.app_name == app_name)
            else:
                query = query.filter(Secret.app_name.is_(None))

            secret = query.first()
            if secret:
                db.delete(secret)
                db.commit()
                return True
            return False
        finally:
            db.close()

    def has_secrets(self) -> bool:
        """
        Check if project has any secrets in database.

        Returns:
            True if secrets exist
        """
        db = self._get_db()
        try:
            count = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.environment == self.environment,
                )
                .count()
            )
            return count > 0
        finally:
            db.close()

    def load_secrets(self):
        """
        Load secrets from database and structure them for Ansible.

        Returns a dict with nested addon structure:
        {
            "shared": {"DOCKER_ORG": "..."},
            "apps": {"api": {"KEY": "..."}},
            "addons": {
                "postgres": {
                    "primary": {
                        "PASSWORD": "...",
                        "USER": "..."
                    }
                }
            }
        }
        """
        db = self._get_db()
        try:
            all_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_name == self.project_name,
                    Secret.environment == self.environment,
                )
                .all()
            )

            # Group by shared/apps/addons
            result = {"shared": {}, "apps": {}, "addons": {}}

            for secret in all_secrets:
                if secret.app_name is None:
                    if secret.source == "addon":
                        # Convert dotted key to nested structure
                        # "postgres.primary.PASSWORD" → addons[postgres][primary][PASSWORD]
                        parts = secret.key.split(".", 2)
                        if len(parts) == 3:
                            addon_type, instance_name, field = parts
                            if addon_type not in result["addons"]:
                                result["addons"][addon_type] = {}
                            if instance_name not in result["addons"][addon_type]:
                                result["addons"][addon_type][instance_name] = {}
                            result["addons"][addon_type][instance_name][field] = (
                                secret.value
                            )
                        else:
                            # Fallback: keep flat if format is unexpected
                            result["addons"][secret.key] = secret.value
                    else:
                        # Shared secrets remain flat
                        result["shared"][secret.key] = secret.value
                else:
                    # App-specific secrets
                    if secret.app_name not in result["apps"]:
                        result["apps"][secret.app_name] = {}
                    result["apps"][secret.app_name][secret.key] = secret.value

            return result
        finally:
            db.close()
