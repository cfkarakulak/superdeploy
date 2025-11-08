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
        """Save secrets to secrets.yml with proper formatting"""
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        # Build formatted YAML manually for better readability
        lines = []

        # Header
        lines.append("# " + "=" * 77)
        lines.append(f"# {self.project_name.upper()} - Secrets Configuration")
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

        secrets_data = secrets.get("secrets", {})

        # Shared secrets
        if "shared" in secrets_data:
            lines.append("")
            lines.append(
                "  # ---------------------------------------------------------------------------"
            )
            lines.append("  # Shared Secrets (available to all applications)")
            lines.append(
                "  # ---------------------------------------------------------------------------"
            )
            lines.append("  shared:")
            shared = secrets_data["shared"]
            if shared:
                # Group by category for better readability
                db_keys = [k for k in shared if k.startswith("POSTGRES_")]
                mq_keys = [k for k in shared if k.startswith("RABBITMQ_")]
                docker_keys = [k for k in shared if k.startswith("DOCKER_")]
                other_keys = [
                    k
                    for k in shared
                    if not any(
                        k.startswith(p) for p in ["POSTGRES_", "RABBITMQ_", "DOCKER_"]
                    )
                ]

                if db_keys:
                    lines.append("")
                    lines.append("    # Database Configuration")
                    for key in sorted(db_keys):
                        lines.append(f"    {key}: {shared[key]}")

                if mq_keys:
                    lines.append("")
                    lines.append("    # Message Queue Configuration")
                    for key in sorted(mq_keys):
                        lines.append(f"    {key}: {shared[key]}")

                if docker_keys:
                    lines.append("")
                    lines.append("    # Docker Registry Configuration")
                    for key in sorted(docker_keys):
                        lines.append(f"    {key}: {shared[key]}")

                if other_keys:
                    lines.append("")
                    lines.append("    # Other Shared Secrets")
                    for key in sorted(other_keys):
                        lines.append(f"    {key}: {shared[key]}")
            else:
                lines.append("    {}")

        # App-specific secrets
        for app_name in secrets_data:
            if app_name != "shared":
                lines.append("")
                lines.append(
                    "  # ---------------------------------------------------------------------------"
                )
                lines.append(f"  # {app_name.upper()} - Application-specific secrets")
                lines.append(
                    "  # ---------------------------------------------------------------------------"
                )
                lines.append(f"  {app_name}:")
                app_secrets = secrets_data[app_name]
                if app_secrets:
                    for key, value in sorted(app_secrets.items()):
                        lines.append(f"    {key}: {value}")
                else:
                    lines.append("    # No app-specific secrets")

        # Environment aliases section
        if "env_aliases" in secrets:
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

            env_aliases = secrets["env_aliases"]
            for app_name in env_aliases:
                lines.append("")
                lines.append(f"  {app_name}:")
                aliases = env_aliases[app_name]
                if aliases:
                    for alias_key, alias_value in sorted(aliases.items()):
                        lines.append(f"    {alias_key}: {alias_value}")
                else:
                    lines.append("    # No aliases needed")

        lines.append("")

        # Write formatted content
        with open(self.secrets_file, "w") as f:
            f.write("\n".join(lines))

        # Set restrictive permissions
        self.secrets_file.chmod(0o600)

    def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """
        Get merged secrets for specific app

        Merges:
        - secrets.shared (all apps)
        - secrets.{app_name} (app-specific)
        - env_aliases.{app_name} (variable name mappings)

        Returns:
            Dict of environment variables for the app
        """
        all_secrets = self.load_secrets()

        # Get structure
        secrets_section = all_secrets.get("secrets", {})
        env_aliases_section = all_secrets.get("env_aliases", {})

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

        # 3. Add env_aliases for this app (maps variable names)
        # Example: DB_HOST: POSTGRES_HOST → DB_HOST=postgres
        app_aliases = env_aliases_section.get(app_name, {})
        if app_aliases:
            for alias_key, alias_value in app_aliases.items():
                # If alias_value is a reference to another variable (uppercase with underscore)
                if (
                    isinstance(alias_value, str)
                    and alias_value.isupper()
                    and "_" in alias_value
                ):
                    # Look up the actual value from merged secrets
                    if alias_value in merged:
                        merged[alias_key] = merged[alias_value]
                else:
                    # It's a static value
                    merged[alias_key] = alias_value

        return merged
