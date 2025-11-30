"""
Configuration Management Service

Centralized config loading, validation, and queries.
Used by 25+ commands that need project config access.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from cli.core.config_loader import ProjectConfig
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
    Centralized DB-based configuration management service.

    Responsibilities:
    - Load and cache project configs from database
    - App configuration queries
    - VM configuration queries
    - Project validation

    ALL DATA FROM DATABASE - NO FILE OPERATIONS
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._config_cache: Dict[str, Any] = {}

    def load_project_config(self, project_name: str, force_reload: bool = False):
        """
        Load project configuration from database with caching.

        Args:
            project_name: Project name
            force_reload: Force reload from database

        Returns:
            ProjectConfig object built from database

        Raises:
            FileNotFoundError: If project not found
            ValueError: If config invalid
        """
        if project_name not in self._config_cache or force_reload:
            # Load from database ONLY - no file fallback
            from cli.database import get_db_session, Project

            db = get_db_session()
            try:
                db_project = (
                    db.query(Project).filter(Project.name == project_name).first()
                )

                if not db_project:
                    raise FileNotFoundError(
                        f"Project '{project_name}' not found in database\n"
                        f"Available projects: {', '.join(self.list_projects())}\n"
                        f"Or run: superdeploy {project_name}:init"
                    )

                # Build config from database
                config_dict = self._build_config_from_db(db_project, db)

                # Convert to ProjectConfig object
                config = ProjectConfig(project_name, config_dict, from_db=True)
                self._config_cache[project_name] = config

            finally:
                db.close()

        return self._config_cache[project_name]

    def _build_config_from_db(self, db_project, db) -> Dict[str, Any]:
        """Build config dictionary from database records."""
        from cli.database import App, Addon, VM

        # Base config
        config = {
            "project": {
                "name": db_project.name,
                "description": db_project.description or f"{db_project.name} project",
                "domain": db_project.domain,
            },
            "gcp": {
                "project_id": db_project.gcp_project,
                "region": db_project.gcp_region or DEFAULT_GCP_REGION,
                "zone": db_project.gcp_zone or DEFAULT_GCP_ZONE,
            },
            "github": {
                "organization": db_project.github_org,
            },
            "ssh": {
                "key_path": db_project.ssh_key_path or DEFAULT_SSH_KEY_PATH,
                "public_key_path": db_project.ssh_public_key_path
                or DEFAULT_SSH_PUBLIC_KEY_PATH,
                "user": db_project.ssh_user or DEFAULT_SSH_USER,
            },
            "docker": {
                "registry": db_project.docker_registry or "docker.io",
                "organization": db_project.docker_organization,
            },
            "network": {
                "vpc_subnet": db_project.vpc_subnet or "10.1.0.0/16",
                "docker_subnet": db_project.docker_subnet or "172.30.0.0/24",
            },
            "ssl": {
                "email": db_project.ssl_email,
            },
        }

        # Apps
        apps = {}
        db_apps = db.query(App).filter(App.project_id == db_project.id).all()
        for app in db_apps:
            apps[app.name] = {
                "path": app.path,
                "vm": app.vm or "app",
                "port": app.port,
            }
        config["apps"] = apps

        # VMs
        vms = {}
        db_vms = db.query(VM).filter(VM.project_id == db_project.id).all()
        for vm in db_vms:
            vms[vm.role] = {
                "count": vm.count,
                "machine_type": vm.machine_type,
                "disk_size": vm.disk_size,
            }
        config["vms"] = vms

        # Addons - group by category
        addons = {}
        db_addons = db.query(Addon).filter(Addon.project_id == db_project.id).all()
        for addon in db_addons:
            if addon.category not in addons:
                addons[addon.category] = {}

            addons[addon.category][addon.instance_name] = {
                "type": addon.type,
                "version": addon.version,
                "vm": addon.vm,
                "plan": addon.plan,
            }
        config["addons"] = addons

        return config

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
        Get SSH configuration from database.

        Args:
            project_name: Project name

        Returns:
            SSH config with key_path, user, etc.
        """
        # Read SSH config directly from database (not file-based config)
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()
        try:
            result = db.execute(
                text("""
                    SELECT ssh_key_path, ssh_public_key_path, ssh_user
                    FROM projects
                    WHERE name = :project_name
                """),
                {"project_name": project_name},
            )
            row = result.fetchone()

            if row:
                return {
                    "key_path": row[0] or DEFAULT_SSH_KEY_PATH,
                    "public_key_path": row[1] or DEFAULT_SSH_PUBLIC_KEY_PATH,
                    "user": row[2] or DEFAULT_SSH_USER,
                }
        finally:
            db.close()

        # Fallback to defaults if not in database
        return {
            "key_path": DEFAULT_SSH_KEY_PATH,
            "public_key_path": DEFAULT_SSH_PUBLIC_KEY_PATH,
            "user": DEFAULT_SSH_USER,
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
        List all available projects from database ONLY.

        Returns:
            List of project names
        """
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            projects = db.query(Project.name).all()
            project_names = [p.name for p in projects]
            return sorted(project_names)
        finally:
            db.close()

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
