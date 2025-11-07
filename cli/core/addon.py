"""Addon data model and rendering logic"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import yaml
from jinja2 import Template


@dataclass
class Addon:
    """Represents a loaded addon with metadata, templates, and rendering methods"""

    name: str
    metadata: dict
    compose_template: Template
    env_schema: dict
    ansible_tasks: dict
    addon_path: Path

    def render_compose(self, context: dict) -> dict:
        """
        Render compose template with context variables.

        Args:
            context: Dictionary containing template variables like project_name, addon_name, etc.

        Returns:
            Dictionary containing the rendered Docker compose service configuration
        """
        rendered = self.compose_template.render(**context)
        return yaml.safe_load(rendered)

    def get_env_vars(self, project_config: dict) -> Dict[str, str]:
        """
        Get environment variables for this addon with project-specific substitutions.

        Args:
            project_config: Project configuration dictionary

        Returns:
            Dictionary of environment variable names to values
        """
        env_vars = {}
        # Extract project name from nested structure
        project_info = project_config.get("project", {})
        if isinstance(project_info, dict):
            project_name = project_info.get("name", "")
        else:
            project_name = str(project_info)

        # Get addon-specific config from project.yml
        addon_config = project_config.get("addons", {}).get(self.name, {})

        for var_name, var_config in self.env_schema.get("variables", {}).items():
            source = var_config.get("source", "config")
            value = var_config.get("value", "")

            # Get value based on source type
            if source == "config":
                # Try to get from addon-specific config first (most direct)
                config_key = var_name.replace(f"{self.name.upper()}_", "").lower()
                if config_key in addon_config:
                    value = str(addon_config[config_key])
                else:
                    # Try from_project path if specified
                    from_project = var_config.get("from_project", "")
                    if from_project:
                        # Parse path like "infrastructure.forgejo.port"
                        parts = from_project.split(".")
                        config_value = project_config
                        for part in parts:
                            config_value = (
                                config_value.get(part, {})
                                if isinstance(config_value, dict)
                                else {}
                            )

                        if config_value and not isinstance(config_value, dict):
                            value = str(config_value)
                        else:
                            # Fallback to default
                            value = str(var_config.get("default", value))
                    else:
                        # Use default value
                        value = str(var_config.get("default", value))

            elif source == "secret":
                # Secrets are referenced as ${VAR_NAME} - they'll be substituted at runtime
                value = var_config.get("value", f"${{{var_name}}}")

            elif source == "runtime":
                # Runtime values like ${ANSIBLE_HOST} - keep as placeholder
                value = var_config.get("value", "")

            # Substitute common placeholders
            value = value.replace("${PROJECT}", project_name)

            # Handle CORE_INTERNAL_IP substitution
            if "${CORE_INTERNAL_IP}" in value:
                core_ip = self._get_core_ip(project_config)
                value = value.replace("${CORE_INTERNAL_IP}", core_ip)

            env_vars[var_name] = value

        return env_vars

    def get_github_secrets(self) -> List[str]:
        """
        Get list of GitHub secrets this addon needs.

        Returns:
            List of secret names
        """
        return self.env_schema.get("github_secrets", [])

    def get_dependencies(self) -> List[str]:
        """
        Get list of addon dependencies.

        Returns:
            List of addon names that this addon requires
        """
        return self.metadata.get("requires", [])

    def get_conflicts(self) -> List[str]:
        """
        Get list of conflicting addons.

        Returns:
            List of addon names that conflict with this addon
        """
        return self.metadata.get("conflicts", [])

    def is_shared(self) -> bool:
        """
        Check if this is a shared addon (single instance across all projects).

        Returns:
            True if addon is shared, False otherwise
        """
        return self.metadata.get("shared", False)

    def get_version(self) -> str:
        """
        Get addon version.

        Returns:
            Version string
        """
        return self.metadata.get("version", "latest")

    def get_category(self) -> str:
        """
        Get addon category.

        Returns:
            Category string (database, cache, queue, proxy, monitoring, etc.)
        """
        return self.metadata.get("category", "other")

    def get_description(self) -> str:
        """
        Get addon description.

        Returns:
            Description string
        """
        return self.metadata.get("description", "")

    def get_env_var_names(self) -> List[str]:
        """
        Get list of environment variable names defined by this addon.

        Returns:
            List of environment variable names
        """
        env_vars = self.metadata.get("env_vars", [])
        names = []

        for var in env_vars:
            if isinstance(var, dict) and "name" in var:
                names.append(var["name"])

        return names

    def get_env_vars_for_template(self) -> List[str]:
        """
        Get environment variable names for workflow templates.

        Returns:
            List of environment variable names
        """
        return self.get_env_var_names()

    def get_secret_vars(self) -> List[str]:
        """
        Get list of secret environment variable names.

        Returns:
            List of secret variable names
        """
        env_vars = self.metadata.get("env_vars", [])
        secrets = []

        for var in env_vars:
            if isinstance(var, dict) and var.get("secret", False):
                secrets.append(var["name"])

        return secrets

    def get_env_var_structure(self) -> Dict[str, str]:
        """
        Get environment variable structure for sync patterns.
        Maps generic keys (host, port, user, password) to actual variable names.

        Returns:
            Dictionary mapping generic keys to variable names
        """
        structure = {}
        env_vars = self.metadata.get("env_vars", [])

        for var in env_vars:
            if isinstance(var, dict) and "name" in var:
                var_name = var["name"]
                # Extract key from variable name (e.g., POSTGRES_HOST -> host)
                parts = var_name.split("_")
                if len(parts) > 1:
                    key = parts[-1].lower()
                    structure[key] = var_name

        return structure

    def _get_core_ip(self, project_config: dict) -> str:
        """
        Extract core VM internal IP from project configuration.

        Args:
            project_config: Project configuration dictionary

        Returns:
            Core VM IP address or placeholder
        """
        # Extract from network subnet if available
        subnet = project_config.get("network", {}).get("subnet", "")
        if subnet:
            # Parse subnet and return first usable IP (e.g., 172.20.0.0/24 -> 172.20.0.2)
            base = subnet.split("/")[0]
            parts = base.split(".")
            parts[-1] = "2"  # Use .2 as core VM IP
            return ".".join(parts)

        return "${CORE_INTERNAL_IP}"  # Fallback placeholder
