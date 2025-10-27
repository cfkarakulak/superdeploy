"""Template merger for combining addon snippets into deployment files"""

from typing import Dict, List
import yaml

from .addon import Addon


class TemplateMerger:
    """Merges addon templates into final deployment files"""

    def __init__(self):
        """Initialize the template merger"""
        pass

    def merge_compose(self, addons: Dict[str, Addon], project_config: dict) -> str:
        """
        Merge Docker compose snippets from all addons into a single compose file.

        Args:
            addons: Dictionary mapping addon names to Addon instances
            project_config: Project configuration dictionary

        Returns:
            String containing the complete docker-compose.core.yml content
        """
        project_name = project_config.get("project", "project")
        network_subnet = project_config.get("network", {}).get(
            "docker_subnet", "172.30.0.0/24"
        )

        # Initialize compose structure
        compose = {
            "version": "3.8",
            "networks": {
                f"{project_name}-network": {
                    "name": f"{project_name}-network",
                    "driver": "bridge",
                    "ipam": {"config": [{"subnet": network_subnet}]},
                }
            },
            "volumes": {},
            "services": {},
        }

        # Merge each addon
        for addon_name, addon in addons.items():
            # Get addon-specific config from project (check both infrastructure and core_services)
            addon_config = project_config.get("infrastructure", {}).get(
                addon_name, {}
            ) or project_config.get("core_services", {}).get(addon_name, {})

            # Build template context with proper variable naming
            # Convert config keys to uppercase for template variables (e.g., port -> FORGEJO_PORT)
            template_vars = {}
            for key, value in addon_config.items():
                # Convert to uppercase template variable name
                var_name = f"{addon_name.upper()}_{key.upper()}"
                template_vars[var_name] = value

            # Build template context
            context = {
                "project_name": project_name,
                "addon_name": addon_name,
                "version": addon_config.get("version", addon.get_version()),
                "healthcheck": addon.metadata.get("healthcheck", {}),
                "monitoring": addon.metadata.get("monitoring", {}),
                "resources": addon.metadata.get("resources", {}),
                **addon.metadata,
                **addon_config,
                **template_vars,
            }

            # Render compose template
            rendered = addon.render_compose(context)

            # Handle different template formats:
            # 1. Full compose file with networks, volumes, services
            # 2. Just services section
            # 3. Single service config

            if "services" in rendered:
                # Full compose file or services section
                for service_name, service_config in rendered["services"].items():
                    compose["services"][service_name] = service_config

                # Merge volumes if present
                if "volumes" in rendered:
                    for volume_name, volume_config in rendered["volumes"].items():
                        # Prefix volume name with project if not already prefixed
                        if not volume_name.startswith(project_name):
                            prefixed_name = f"{project_name}-{volume_name}"
                            compose["volumes"][volume_name] = {"name": prefixed_name}
                        else:
                            compose["volumes"][volume_name] = volume_config or {}

                # Merge networks if present (but keep project network as primary)
                if "networks" in rendered:
                    for network_name, network_config in rendered["networks"].items():
                        if network_name != f"{project_name}-network":
                            compose["networks"][network_name] = network_config
            elif addon_name in rendered:
                # Service wrapped with addon name
                compose["services"][addon_name] = rendered[addon_name]
            else:
                # Direct service config
                compose["services"][addon_name] = rendered

        # Convert to YAML string
        return yaml.dump(compose, default_flow_style=False, sort_keys=False)

    def merge_env(self, addons: Dict[str, Addon], project_config: dict) -> str:
        """
        Merge environment variables from all addons into .env.superdeploy file.

        Args:
            addons: Dictionary mapping addon names to Addon instances
            project_config: Project configuration dictionary

        Returns:
            String containing the complete .env.superdeploy content
        """
        project_name = project_config.get("project", "project")

        lines = [
            "# SuperDeploy - Production Environment Overrides",
            f"# Project: {project_name}",
            "# Auto-generated by: superdeploy generate",
            "#",
            "# These values OVERRIDE your local .env in production",
            "",
        ]

        # Add environment variables from each addon
        for addon_name, addon in addons.items():
            description = addon.get_description()
            lines.append(f"# {description}")

            # Get environment variables with project-specific substitutions
            env_vars = addon.get_env_vars(project_config)

            for var_name, var_value in env_vars.items():
                lines.append(f"{var_name}={var_value}")

            lines.append("")  # Blank line between addons

        return "\n".join(lines)

    def merge_workflow_env(self, addons: Dict[str, Addon]) -> List[str]:
        """
        Generate GitHub Actions workflow env section from addon secrets.

        Args:
            addons: Dictionary mapping addon names to Addon instances

        Returns:
            List of strings representing env variable lines for workflow YAML
        """
        env_lines = []

        # Collect all GitHub secrets from addons
        for addon_name, addon in addons.items():
            secrets = addon.get_github_secrets()

            for secret in secrets:
                # Format as GitHub Actions env variable
                env_lines.append(f"    {secret}: ${{{{ secrets.{secret} }}}}")

        return env_lines

    def merge_ansible_tasks(
        self, addons: Dict[str, Addon], project_config: dict
    ) -> List[dict]:
        """
        Merge Ansible tasks from all addons.

        Args:
            addons: Dictionary mapping addon names to Addon instances
            project_config: Project configuration dictionary

        Returns:
            List of Ansible task dictionaries
        """
        project_name = project_config.get("project", "project")
        all_tasks = []

        for addon_name, addon in addons.items():
            # Get addon-specific config (check both infrastructure and core_services)
            addon_config = project_config.get("infrastructure", {}).get(
                addon_name, {}
            ) or project_config.get("core_services", {}).get(addon_name, {})

            # Get tasks from addon
            tasks = (
                addon.ansible_tasks.copy()
                if isinstance(addon.ansible_tasks, list)
                else []
            )

            # Substitute variables in tasks
            for task in tasks:
                task = self._substitute_ansible_vars(
                    task,
                    {
                        "addon_name": addon_name,
                        "project_name": project_name,
                        "version": addon_config.get("version", addon.get_version()),
                        **addon.metadata.get("healthcheck", {}),
                    },
                )
                all_tasks.append(task)

        return all_tasks

    def _substitute_ansible_vars(self, task: dict, context: dict) -> dict:
        """
        Recursively substitute variables in Ansible task dictionary.

        Args:
            task: Ansible task dictionary
            context: Variables to substitute

        Returns:
            Task dictionary with substituted variables
        """
        if isinstance(task, dict):
            return {
                k: self._substitute_ansible_vars(v, context) for k, v in task.items()
            }
        elif isinstance(task, list):
            return [self._substitute_ansible_vars(item, context) for item in task]
        elif isinstance(task, str):
            # Simple variable substitution
            result = task
            for key, value in context.items():
                result = result.replace(f"{{{{ {key} }}}}", str(value))
            return result
        else:
            return task
