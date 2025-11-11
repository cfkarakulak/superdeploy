"""
Secret Configuration Models

Dataclass models for secret management.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class SharedSecrets:
    """Shared secrets available to all applications."""

    values: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set a secret value."""
        self.values[key] = value

    def has(self, key: str) -> bool:
        """Check if secret exists."""
        return key in self.values

    def __len__(self) -> int:
        return len(self.values)

    def __repr__(self) -> str:
        return f"SharedSecrets(count={len(self.values)})"


@dataclass
class AppSecrets:
    """Application-specific secrets."""

    app_name: str
    values: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set a secret value."""
        self.values[key] = value

    def has(self, key: str) -> bool:
        """Check if secret exists."""
        return key in self.values

    def __len__(self) -> int:
        return len(self.values)

    def __repr__(self) -> str:
        return f"AppSecrets(app={self.app_name}, count={len(self.values)})"


@dataclass
class SecretConfig:
    """Complete secret configuration for a project."""

    project_name: str
    shared: SharedSecrets = field(default_factory=SharedSecrets)
    addons: Dict[str, Dict[str, Dict[str, str]]] = field(
        default_factory=dict
    )  # addons.{type}.{name}.{credential}
    apps: Dict[str, AppSecrets] = field(default_factory=dict)
    env_aliases: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def get_app_secrets(self, app_name: str) -> AppSecrets:
        """Get secrets for specific app."""
        if app_name not in self.apps:
            self.apps[app_name] = AppSecrets(app_name=app_name)
        return self.apps[app_name]

    def get_merged_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for an app (shared + app-specific + aliases).

        Merge order:
        1. Shared secrets (available to all)
        2. App-specific secrets (override shared)
        3. Environment variable aliases (map variable names)

        Args:
            app_name: Name of the application

        Returns:
            Dictionary of merged environment variables
        """
        merged: Dict[str, str] = {}

        # 1. Add shared secrets
        merged.update(self.shared.values)

        # 2. Add app-specific secrets (overrides shared)
        if app_name in self.apps:
            merged.update(self.apps[app_name].values)

        # 3. Add env aliases for this app
        app_aliases = self.env_aliases.get(app_name, {})
        for alias_key, alias_value in app_aliases.items():
            # If it's a reference to another variable (UPPERCASE with _)
            if (
                isinstance(alias_value, str)
                and alias_value.isupper()
                and "_" in alias_value
            ):
                # Look up the actual value
                if alias_value in merged:
                    merged[alias_key] = merged[alias_value]
            else:
                # It's a static value
                merged[alias_key] = alias_value

        return merged

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result: Dict = {
            "secrets": {
                "shared": self.shared.values,
            }
        }

        # Add addon credentials
        if self.addons:
            result["secrets"]["addons"] = self.addons

        # Add app-specific secrets
        for app_name, app_secrets in self.apps.items():
            if app_secrets.values:
                result["secrets"][app_name] = app_secrets.values

        # Add env aliases
        if self.env_aliases:
            result["env_aliases"] = self.env_aliases

        return result

    @classmethod
    def from_dict(cls, project_name: str, data: Dict) -> "SecretConfig":
        """Create from dictionary."""
        secrets_data = data.get("secrets", {})

        # Extract shared secrets
        shared = SharedSecrets(values=secrets_data.get("shared", {}))

        # Extract addon credentials
        addons = secrets_data.get("addons", {})

        # Extract app-specific secrets
        apps: Dict[str, AppSecrets] = {}
        for key, value in secrets_data.items():
            if key not in ["shared", "addons", "apps"] and isinstance(value, dict):
                apps[key] = AppSecrets(app_name=key, values=value)

        # Also check for explicit "apps" key
        if "apps" in secrets_data:
            for app_name, app_values in secrets_data["apps"].items():
                if isinstance(app_values, dict):
                    apps[app_name] = AppSecrets(app_name=app_name, values=app_values)

        # Extract env aliases
        env_aliases = data.get("env_aliases", {})

        return cls(
            project_name=project_name,
            shared=shared,
            addons=addons,
            apps=apps,
            env_aliases=env_aliases,
        )

    def __repr__(self) -> str:
        return f"SecretConfig(project={self.project_name}, shared={len(self.shared)}, apps={len(self.apps)})"
