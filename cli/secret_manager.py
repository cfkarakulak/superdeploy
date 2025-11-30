"""
Secret Management

Database-backed secret manager.
All secrets are stored in PostgreSQL with proper FK relationships.
"""

import re
from pathlib import Path
from typing import Dict, Optional
from cli.database import get_db_session, Secret, SecretAlias, Project, App, VM
from sqlalchemy.orm import Session


class SecretManager:
    """
    Database-backed secret manager.

    All operations work with PostgreSQL database using FK relationships.
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
        self._project_id: Optional[int] = None

    def _get_db(self) -> Session:
        """Get database session."""
        return get_db_session()

    def _get_project_id(self, db: Session) -> Optional[int]:
        """Get project ID from project name."""
        if self._project_id is not None:
            return self._project_id

        project = db.query(Project).filter(Project.name == self.project_name).first()
        if project:
            self._project_id = project.id
        return self._project_id

    def _get_app_id(self, db: Session, app_name: str) -> Optional[int]:
        """Get app ID from app name."""
        project_id = self._get_project_id(db)
        if not project_id:
            return None

        app = (
            db.query(App)
            .filter(App.project_id == project_id, App.name == app_name)
            .first()
        )
        return app.id if app else None

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

        project_id = self._get_project_id(db)
        if not project_id:
            return None

        # The alias points to an addon secret key
        # postgres.primary.HOST is stored as key in secrets table
        secret = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.key == alias_value,
                Secret.environment == self.environment,
            )
            .first()
        )

        return secret.value if secret else None

    def _resolve_template(self, template: str, db: Session) -> str:
        """
        Resolve template placeholders like {{ APP_0_EXTERNAL_IP }}.

        Args:
            template: Template string with {{ PLACEHOLDER }} syntax
            db: Database session

        Returns:
            Resolved string
        """
        project_id = self._get_project_id(db)
        if not project_id:
            return template

        # Find all {{ VAR_NAME }} patterns
        pattern = r"\{\{\s*([A-Z0-9_]+)\s*\}\}"

        def replace_placeholder(match):
            var_name = match.group(1)

            # Check if it's a VM IP variable (e.g., APP_0_EXTERNAL_IP, CORE_0_INTERNAL_IP)
            vm_pattern = r"([A-Z]+)_(\d+)_(EXTERNAL|INTERNAL)_IP"
            vm_match = re.match(vm_pattern, var_name)
            if vm_match:
                role = vm_match.group(1).lower()  # app, core, etc.
                ip_type = vm_match.group(3).lower()  # external or internal

                # Get VM from database
                vm = (
                    db.query(VM)
                    .filter(VM.project_id == project_id, VM.role == role)
                    .first()
                )
                if vm:
                    if ip_type == "external" and vm.external_ip:
                        return vm.external_ip
                    elif ip_type == "internal" and vm.internal_ip:
                        return vm.internal_ip

            # Check shared secrets
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.app_id.is_(None),
                    Secret.key == var_name,
                    Secret.environment == self.environment,
                )
                .first()
            )
            if secret:
                return secret.value

            # Return original if not found
            return match.group(0)

        return re.sub(pattern, replace_placeholder, template)

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for specific app with alias resolution.

        Merges:
        - Shared secrets (app_id=NULL)
        - Addon secrets (source='addon')
        - App-specific secrets (app_id={app})
        - Resolves aliases

        Args:
            app_name: Name of the application

        Returns:
            Dictionary of environment variables for the app
        """
        db = self._get_db()
        try:
            project_id = self._get_project_id(db)
            if not project_id:
                return {}

            app_id = self._get_app_id(db, app_name)
            merged = {}

            # 1. Get shared secrets (app_id=NULL)
            shared_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.app_id.is_(None),
                    Secret.environment == self.environment,
                )
                .all()
            )

            for secret in shared_secrets:
                merged[secret.key] = secret.value

            # 2. Get app-specific secrets (if app exists)
            if app_id:
                app_secrets = (
                    db.query(Secret)
                    .filter(
                        Secret.project_id == project_id,
                        Secret.app_id == app_id,
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
                        SecretAlias.project_id == project_id,
                        SecretAlias.app_id == app_id,
                    )
                    .all()
                )

                # Collect target keys that will be replaced by aliases
                target_keys_to_remove = []

                for alias in aliases:
                    # Resolve alias to actual value
                    resolved_value = self._resolve_alias(alias.target_key, db)
                    if resolved_value:
                        merged[alias.alias_key] = resolved_value
                        # Mark target key for removal
                        target_keys_to_remove.append(alias.target_key)

                # Remove target keys from merged dict
                for target_key in target_keys_to_remove:
                    merged.pop(target_key, None)

            return merged

        finally:
            db.close()

    def get_app_secrets_with_templates(
        self, app_name: str, env_templates: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Get merged secrets with template resolution.

        Args:
            app_name: Name of the application
            env_templates: Templates from marker file (e.g., {"NEXT_PUBLIC_API_URL": "http://{{ APP_0_EXTERNAL_IP }}:8000"})

        Returns:
            Dictionary of environment variables with resolved templates
        """
        db = self._get_db()
        try:
            # Get base secrets
            merged = self.get_app_secrets(app_name)

            # Resolve templates and add to merged
            for key, template in env_templates.items():
                resolved = self._resolve_template(template, db)
                merged[key] = resolved

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
            project_id = self._get_project_id(db)
            if not project_id:
                return {}

            secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.app_id.is_(None),
                    Secret.environment == self.environment,
                )
                .all()
            )

            return {s.key: s.value for s in secrets}
        finally:
            db.close()

    def set_shared_secret(self, key: str, value: str, source: str = "shared") -> None:
        """
        Set a shared secret value.

        Args:
            key: Secret key name
            value: Secret value
            source: Secret source (shared/addon)
        """
        db = self._get_db()
        try:
            project_id = self._get_project_id(db)
            if not project_id:
                raise ValueError(f"Project '{self.project_name}' not found")

            # Upsert (update or insert)
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.app_id.is_(None),
                    Secret.key == key,
                    Secret.environment == self.environment,
                )
                .first()
            )

            if secret:
                secret.value = value
                secret.source = source
            else:
                secret = Secret(
                    project_id=project_id,
                    app_id=None,
                    key=key,
                    value=value,
                    environment=self.environment,
                    source=source,
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
            project_id = self._get_project_id(db)
            if not project_id:
                raise ValueError(f"Project '{self.project_name}' not found")

            app_id = self._get_app_id(db, app_name)
            if not app_id:
                raise ValueError(f"App '{app_name}' not found in project")

            # Upsert (update or insert)
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.app_id == app_id,
                    Secret.key == key,
                    Secret.environment == self.environment,
                )
                .first()
            )

            if secret:
                secret.value = value
            else:
                secret = Secret(
                    project_id=project_id,
                    app_id=app_id,
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
            project_id = self._get_project_id(db)
            if not project_id:
                return False

            query = db.query(Secret).filter(
                Secret.project_id == project_id,
                Secret.key == key,
                Secret.environment == self.environment,
            )

            if app_name:
                app_id = self._get_app_id(db, app_name)
                if not app_id:
                    return False
                query = query.filter(Secret.app_id == app_id)
            else:
                query = query.filter(Secret.app_id.is_(None))

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
            project_id = self._get_project_id(db)
            if not project_id:
                return False

            count = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
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
            project_id = self._get_project_id(db)
            if not project_id:
                return {"shared": {}, "apps": {}, "addons": {}}

            # Get all secrets for project
            all_secrets = (
                db.query(Secret)
                .filter(
                    Secret.project_id == project_id,
                    Secret.environment == self.environment,
                )
                .all()
            )

            # Get app id to name mapping
            apps = db.query(App).filter(App.project_id == project_id).all()
            app_id_to_name = {app.id: app.name for app in apps}

            # Group by shared/apps/addons
            result = {"shared": {}, "apps": {}, "addons": {}}

            for secret in all_secrets:
                if secret.app_id is None:
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
                    app_name = app_id_to_name.get(secret.app_id)
                    if app_name:
                        if app_name not in result["apps"]:
                            result["apps"][app_name] = {}
                        result["apps"][app_name][secret.key] = secret.value

            return result
        finally:
            db.close()

    def set_alias(self, app_name: str, alias_key: str, target_key: str) -> None:
        """
        Set an alias for an app.

        Args:
            app_name: Name of the application
            alias_key: Alias key (e.g., DB_HOST)
            target_key: Target key (e.g., postgres.primary.HOST)
        """
        db = self._get_db()
        try:
            project_id = self._get_project_id(db)
            if not project_id:
                raise ValueError(f"Project '{self.project_name}' not found")

            app_id = self._get_app_id(db, app_name)
            if not app_id:
                raise ValueError(f"App '{app_name}' not found in project")

            # Upsert
            alias = (
                db.query(SecretAlias)
                .filter(
                    SecretAlias.project_id == project_id,
                    SecretAlias.app_id == app_id,
                    SecretAlias.alias_key == alias_key,
                )
                .first()
            )

            if alias:
                alias.target_key = target_key
            else:
                alias = SecretAlias(
                    project_id=project_id,
                    app_id=app_id,
                    alias_key=alias_key,
                    target_key=target_key,
                )
                db.add(alias)

            db.commit()
        finally:
            db.close()

    def get_aliases(self, app_name: str) -> Dict[str, str]:
        """
        Get all aliases for an app.

        Args:
            app_name: Name of the application

        Returns:
            Dictionary of alias_key -> target_key
        """
        db = self._get_db()
        try:
            project_id = self._get_project_id(db)
            if not project_id:
                return {}

            app_id = self._get_app_id(db, app_name)
            if not app_id:
                return {}

            aliases = (
                db.query(SecretAlias)
                .filter(
                    SecretAlias.project_id == project_id,
                    SecretAlias.app_id == app_id,
                )
                .all()
            )

            return {a.alias_key: a.target_key for a in aliases}
        finally:
            db.close()
