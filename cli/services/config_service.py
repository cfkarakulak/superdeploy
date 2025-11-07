"""
Configuration Management Service

Centralized config loading, validation, and queries.
Used by 25+ commands that need project config access.
"""

from pathlib import Path
from typing import Dict, Any, List
from cli.core.config_loader import ConfigLoader
from cli.constants import (
    DEFAULT_SSH_KEY_PATH,
    DEFAULT_SSH_PUBLIC_KEY_PATH,
    DEFAULT_SSH_USER,
    DEFAULT_GCP_REGION,
    DEFAULT_GCP_ZONE,
    DEFAULT_APP_PORT,
    DEFAULT_DOCKER_REGISTRY,
)


class ConfigService:
    """
    Centralized configuration management service.

    Responsibilities:
    - Load and cache project configs
    - App configuration queries
    - VM configuration queries
    - Project validation
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.projects_dir = project_root / "projects"
        self.config_loader = ConfigLoader(self.projects_dir)
        self._config_cache: Dict[str, Any] = {}

    def load_project_config(self, project_name: str, force_reload: bool = False):
        """
        Load project configuration with caching.

        Args:
            project_name: Project name
            force_reload: Force reload from disk

        Returns:
            ProjectConfig object

        Raises:
            FileNotFoundError: If project not found
            ValueError: If config invalid
        """
        if project_name not in self._config_cache or force_reload:
            try:
                config = self.config_loader.load_project(project_name)
                self._config_cache[project_name] = config
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Project '{project_name}' not found\n"
                    f"Available projects: {', '.join(self.list_projects())}\n"
                    f"Or run: superdeploy init -p {project_name}"
                )

        return self._config_cache[project_name]

    def get_raw_config(self, project_name: str) -> Dict[str, Any]:
        """
        Get raw config dictionary.

        Args:
            project_name: Project name

        Returns:
            Raw config dictionary
        """
        config = self.load_project_config(project_name)
        return config.raw_config

    def get_app_config(self, project_name: str, app_name: str) -> Dict[str, Any]:
        """
        Get app configuration.

        Args:
            project_name: Project name
            app_name: App name

        Returns:
            App config dictionary

        Raises:
            KeyError: If app not found
        """
        config = self.get_raw_config(project_name)
        apps = config.get("apps", {})

        if app_name not in apps:
            raise KeyError(
                f"App '{app_name}' not found in project '{project_name}'\n"
                f"Available apps: {', '.join(apps.keys())}"
            )

        return apps[app_name]

    def get_app_vm_role(self, project_name: str, app_name: str) -> str:
        """
        Get VM role for app.

        Args:
            project_name: Project name
            app_name: App name

        Returns:
            VM role string (e.g., "core", "app")
        """
        app_config = self.get_app_config(project_name, app_name)
        return app_config.get("vm", "core")

    def get_app_port(self, project_name: str, app_name: str) -> int:
        """
        Get app port.

        Args:
            project_name: Project name
            app_name: App name

        Returns:
            Port number
        """
        app_config = self.get_app_config(project_name, app_name)
        return app_config.get("port", DEFAULT_APP_PORT)

    def get_app_path(self, project_name: str, app_name: str) -> Path:
        """
        Get app path as Path object.

        Args:
            project_name: Project name
            app_name: App name

        Returns:
            App path
        """
        app_config = self.get_app_config(project_name, app_name)
        path_str = app_config.get("path", "")
        return Path(path_str).expanduser().resolve()

    def get_ssh_config(self, project_name: str) -> Dict[str, str]:
        """
        Get SSH configuration.

        Args:
            project_name: Project name

        Returns:
            SSH config with key_path, user, etc.
        """
        config = self.get_raw_config(project_name)
        ssh_config = config.get("cloud", {}).get("ssh", {})

        # Defaults from constants
        return {
            "key_path": ssh_config.get("key_path", DEFAULT_SSH_KEY_PATH),
            "public_key_path": ssh_config.get(
                "public_key_path", DEFAULT_SSH_PUBLIC_KEY_PATH
            ),
            "user": ssh_config.get("user", DEFAULT_SSH_USER),
        }

    def get_gcp_config(self, project_name: str) -> Dict[str, str]:
        """
        Get GCP configuration.

        Args:
            project_name: Project name

        Returns:
            GCP config with project_id, region, zone
        """
        config = self.get_raw_config(project_name)
        gcp_config = config.get("cloud", {}).get("gcp", {})

        return {
            "project_id": gcp_config.get("project_id", ""),
            "region": gcp_config.get("region", DEFAULT_GCP_REGION),
            "zone": gcp_config.get("zone", DEFAULT_GCP_ZONE),
        }

    def get_addons(self, project_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get addons configuration.

        Args:
            project_name: Project name

        Returns:
            Addons config dictionary
        """
        config_obj = self.load_project_config(project_name)
        return config_obj.get_addons()

    def get_vms(self, project_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get VMs configuration.

        Args:
            project_name: Project name

        Returns:
            VMs config dictionary
        """
        config = self.get_raw_config(project_name)
        return config.get("vms", {})

    def get_network_config(self, project_name: str) -> Dict[str, str]:
        """
        Get network configuration.

        Args:
            project_name: Project name

        Returns:
            Network config with vpc_subnet, docker_subnet
        """
        config_obj = self.load_project_config(project_name)
        return config_obj.get_network_config()

    def list_projects(self) -> List[str]:
        """
        List all available projects.

        Returns:
            List of project names
        """
        return self.config_loader.list_projects()

    def list_apps(self, project_name: str) -> List[str]:
        """
        List all apps in project.

        Args:
            project_name: Project name

        Returns:
            List of app names
        """
        config = self.get_raw_config(project_name)
        return list(config.get("apps", {}).keys())

    def validate_project(self, project_name: str) -> bool:
        """
        Validate project exists and has valid config.

        Args:
            project_name: Project name

        Returns:
            True if valid

        Raises:
            FileNotFoundError: If project not found
            ValueError: If config invalid
        """
        self.load_project_config(project_name)
        return True

    def project_exists(self, project_name: str) -> bool:
        """
        Check if project exists without raising error.

        Args:
            project_name: Project name

        Returns:
            True if exists
        """
        try:
            self.validate_project(project_name)
            return True
        except (FileNotFoundError, ValueError):
            return False

    def get_project_path(self, project_name: str) -> Path:
        """
        Get project directory path.

        Args:
            project_name: Project name

        Returns:
            Project directory path
        """
        return self.projects_dir / project_name

    def get_github_org(self, project_name: str) -> str:
        """
        Get GitHub organization.

        Args:
            project_name: Project name

        Returns:
            GitHub org name
        """
        config = self.get_raw_config(project_name)
        return config.get("github", {}).get("organization", f"{project_name}io")

    def get_docker_config(self, project_name: str) -> Dict[str, str]:
        """
        Get Docker configuration.

        Args:
            project_name: Project name

        Returns:
            Docker config with registry, organization
        """
        config = self.get_raw_config(project_name)
        docker_config = config.get("docker", {})

        return {
            "registry": docker_config.get("registry", DEFAULT_DOCKER_REGISTRY),
            "organization": docker_config.get("organization", ""),
        }

    def clear_cache(self) -> None:
        """Clear config cache."""
        self._config_cache.clear()
