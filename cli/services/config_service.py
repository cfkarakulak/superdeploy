"""
Configuration Management Service

Centralized config loading, validation, and queries.
Used by 25+ commands that need project config access.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from cli.core.config_loader import ConfigLoader
from cli.core.addon_instance import AddonInstance, AddonAttachment
from cli.constants import (
    DEFAULT_SSH_KEY_PATH,
    DEFAULT_SSH_PUBLIC_KEY_PATH,
    DEFAULT_SSH_USER,
    DEFAULT_GCP_REGION,
    DEFAULT_GCP_ZONE,
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
                    f"Or run: superdeploy {project_name}:init"
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

    def get_project_path(self, project_name: str) -> Path:
        """
        Get project directory path.

        Args:
            project_name: Project name

        Returns:
            Project directory path
        """
        return self.projects_dir / project_name

    def parse_addons(self, config: Dict) -> List[AddonInstance]:
        """
        Parse addon instances from config.yml

        Input:
            addons:
              databases:
                primary:
                  type: postgres
                  version: 15-alpine
                  plan: standard

        Output:
            [AddonInstance(category='databases', name='primary', type='postgres', ...)]

        Args:
            config: Project configuration dictionary

        Returns:
            List of AddonInstance objects
        """
        instances = []

        addons_config = config.get("addons", {})

        for category, category_instances in addons_config.items():
            if not isinstance(category_instances, dict):
                continue

            for instance_name, instance_config in category_instances.items():
                if not isinstance(instance_config, dict):
                    continue

                instance = AddonInstance(
                    category=category,
                    name=instance_name,
                    type=instance_config["type"],
                    version=instance_config.get("version", "latest"),
                    plan=instance_config.get("plan", "standard"),
                    options=instance_config.get("options", {}),
                )
                instances.append(instance)

        return instances

    def parse_app_attachments(self, app_config: Dict) -> List[AddonAttachment]:
        """
        Parse app's addon attachments

        Input:
            addons:
              - addon: databases.primary
                as: DATABASE
                access: readwrite
              - databases.analytics  # Simple format

        Output:
            [AddonAttachment(addon='databases.primary', as_='DATABASE', access='readwrite')]

        Args:
            app_config: App configuration dictionary

        Returns:
            List of AddonAttachment objects
        """
        attachments = []

        for attachment_config in app_config.get("addons", []):
            if isinstance(attachment_config, str):
                # Simple format: "databases.primary"
                addon = attachment_config
                as_ = self._default_prefix(addon)
                access = "readwrite"
            else:
                # Full format with options
                addon = attachment_config["addon"]
                as_ = attachment_config.get("as", self._default_prefix(addon))
                access = attachment_config.get("access", "readwrite")

            attachment = AddonAttachment(addon=addon, as_=as_, access=access)
            attachments.append(attachment)

        return attachments

    def get_addon_instance(
        self, project_name: str, category: str, name: str
    ) -> Optional[AddonInstance]:
        """
        Get specific addon instance.

        Args:
            project_name: Project name
            category: Addon category (databases, caches, queues)
            name: Instance name (primary, analytics, etc.)

        Returns:
            AddonInstance if found, None otherwise
        """
        config = self.get_raw_config(project_name)
        instances = self.parse_addons(config)

        for instance in instances:
            if instance.category == category and instance.name == name:
                return instance

        return None

    def _default_prefix(self, addon: str) -> str:
        """
        Get default env var prefix from addon name

        databases.primary → DATABASE
        caches.session → CACHE
        queues.main → QUEUE

        Args:
            addon: Full addon name (category.name)

        Returns:
            Default environment variable prefix
        """
        category = addon.split(".")[0]

        prefix_map = {
            "databases": "DATABASE",
            "caches": "CACHE",
            "queues": "QUEUE",
            "search": "SEARCH",
            "proxy": "PROXY",
        }

        return prefix_map.get(category, category.upper())
