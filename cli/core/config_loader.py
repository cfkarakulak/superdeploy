"""Configuration management for SuperDeploy projects"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List


@dataclass
class VMConfig:
    """Virtual machine configuration"""

    machine_type: str = "e2-medium"
    disk_size: int = 20
    image: str = "debian-cloud/debian-11"


@dataclass
class NetworkConfig:
    """Network configuration"""

    vpc_subnet: str = "10.128.0.0/20"  # GCP VPC subnet (Google Cloud default)
    docker_subnet: str = (
        "172.30.0.0/24"  # Docker container network (avoid 172.17-172.29)
    )


@dataclass
class AppConfig:
    """Application configuration"""

    path: str
    vm: str
    port: int
    replicas: int = 1
    type: str = "web"  # "web" or "worker" - auto-detected if not specified


class ProjectConfig:
    """Represents a loaded and validated project configuration"""

    def __init__(self, project_name: str, config_dict: dict, project_dir: Path = None):
        """
        Initialize project configuration

        Args:
            project_name: Name of the project
            config_dict: Raw configuration dictionary from config.yml
            project_dir: Path to project directory (optional)
        """
        self.project_name = project_name
        self.raw_config = config_dict
        self.project_dir = project_dir
        self.config_path = project_dir / "config.yml" if project_dir else None
        self.project_dir = project_dir
        self._apply_defaults()
        self._validate()

    def _apply_defaults(self) -> None:
        """Apply default values to configuration"""
        # Ensure network section exists with defaults
        if "network" not in self.raw_config:
            self.raw_config["network"] = {}

        # Auto-allocate subnets using SubnetAllocator
        project_name = self.raw_config.get("project", {}).get("name", "unknown")
        subnet_allocated = False

        if "vpc_subnet" not in self.raw_config["network"]:
            from cli.subnet_allocator import SubnetAllocator

            allocator = SubnetAllocator()
            self.raw_config["network"]["vpc_subnet"] = allocator.get_subnet(
                project_name
            )
            subnet_allocated = True

        if "docker_subnet" not in self.raw_config["network"]:
            from cli.subnet_allocator import SubnetAllocator

            allocator = SubnetAllocator()
            self.raw_config["network"]["docker_subnet"] = allocator.get_docker_subnet(
                project_name
            )
            subnet_allocated = True

        # Save allocated subnets back to yaml file for transparency
        if subnet_allocated and self.config_path:
            self._save_config()

        # Note: Monitoring config removed - now only in orchestrator config

    def _save_config(self) -> None:
        """
        Save configuration (DEPRECATED - config now stored in database).

        This method is kept for backward compatibility but does nothing.
        Config changes should be made through database updates.
        """
        # Config is now in database, not in files
        pass

    def _validate(self) -> None:
        """Validate configuration"""
        # Validate required fields
        if "project" not in self.raw_config:
            raise ValueError("Missing required field: 'project'")

        # Project must be a dict with 'name' field
        project_field = self.raw_config["project"]
        if not isinstance(project_field, dict):
            raise ValueError(
                "Invalid 'project' field: must be a dict with 'name', 'description', 'created_at'\n"
                "Example:\n"
                "project:\n"
                "  name: myproject\n"
                "  description: My project\n"
                "  created_at: 2025-10-31T10:00:00"
            )

        if "name" not in project_field:
            raise ValueError("Missing required field: 'project.name'")

        config_project_name = project_field["name"]

        # Validate project name matches
        if config_project_name != self.project_name:
            raise ValueError(
                f"Project name mismatch: config has '{config_project_name}' "
                f"but expected '{self.project_name}'"
            )

        # Validate VM config values
        vm_config = self.get_vm_config()
        if vm_config["disk_size"] <= 0:
            raise ValueError(
                f"Invalid disk_size: {vm_config['disk_size']} (must be > 0)"
            )

        # Validate network subnet formats (basic check)
        network_config = self.get_network_config()
        vpc_subnet = network_config.get("vpc_subnet", "10.128.0.0/20")
        docker_subnet = network_config.get("docker_subnet", "172.30.0.0/24")

        if "/" not in vpc_subnet:
            raise ValueError(
                f"Invalid vpc_subnet format: {vpc_subnet} (expected CIDR notation)"
            )
        if "/" not in docker_subnet:
            raise ValueError(
                f"Invalid docker_subnet format: {docker_subnet} (expected CIDR notation)"
            )

    def get_vm_config(self) -> Dict[str, Any]:
        """
        Get VM configuration with defaults

        Returns:
            Dictionary with machine_type, disk_size, and image
        """
        # VM config is now at top level or use defaults
        vm_config = self.raw_config.get("vm_config", {})
        return {
            "machine_type": vm_config.get("machine_type", "e2-medium"),
            "disk_size": vm_config.get("disk_size", 20),
            "image": vm_config.get("image", "debian-cloud/debian-11"),
        }

    def get_network_config(self) -> Dict[str, Any]:
        """
        Get network configuration

        Returns:
            Dictionary with network settings
        """
        return self.raw_config.get("network", {})

    def get_apps(self) -> Dict[str, Dict[str, Any]]:
        """
        Get application configurations with process definitions from marker files

        Returns:
            Dictionary of application configurations enriched with marker data
        """
        from cli.marker_manager import MarkerManager

        apps = self.raw_config.get("apps", {}).copy()

        # Enrich apps with process definitions from marker files
        for app_name, app_config in apps.items():
            app_path = app_config.get("path")
            if not app_path:
                continue

            # Read marker file to get process definitions
            from pathlib import Path

            app_path_obj = Path(app_path).expanduser().resolve()
            marker_file = app_path_obj / "superdeploy"

            if marker_file.exists():
                try:
                    marker = MarkerManager.load_marker(app_path_obj)
                    # Inject process definitions from marker into app config
                    if marker and marker.processes:
                        # Convert ProcessDefinition objects to dicts for Ansible
                        processes_dict = {}
                        for name, proc_def in marker.processes.items():
                            processes_dict[name] = proc_def.to_dict()
                        app_config["processes"] = processes_dict
                except Exception:
                    # If marker read fails, continue without processes
                    pass

        return apps

    def get_vms(self) -> Dict[str, Dict[str, Any]]:
        """
        Get VM definitions

        Returns:
            Dictionary of VM configurations
        """
        return self.raw_config.get("vms", {})

    def get_monitoring_config(self) -> Dict[str, Any]:
        """
        Get monitoring configuration (combines grafana, prometheus)

        Returns:
            Dictionary with monitoring settings
        """
        return {
            "grafana": self.raw_config.get("grafana", {}),
            "prometheus": self.raw_config.get("prometheus", {}),
        }

    def get_addons(self) -> Dict[str, Dict[str, Any]]:
        """
        Get addon configurations from addons section.

        Returns:
            Dictionary of addon configurations
        """
        return self.raw_config.get("addons", {})

    def to_terraform_vars(self, preserve_ip: bool = False) -> Dict[str, Any]:
        """
        Convert to Terraform variables format

        Dynamically builds vm_groups from config.yml vms section.
        Each VM is created with all its properties.

        Args:
            preserve_ip: Whether to preserve existing static IPs

        Returns:
            Dictionary suitable for Terraform tfvars
        """
        network_config = self.get_network_config()
        vms_config = self.get_vms()
        cloud_config = self.raw_config.get("cloud", {})
        gcp_config = cloud_config.get("gcp", {})
        ssh_config = cloud_config.get("ssh", {})

        # Get unique subnet for this project
        from cli.subnet_allocator import SubnetAllocator

        allocator = SubnetAllocator()
        project_subnet = allocator.get_subnet(self.project_name)

        # Load existing IPs if preserve_ip is enabled
        existing_ips = {}
        if preserve_ip:
            import click
            from cli.state_manager import StateManager
            from cli.utils import get_project_root

            # Load IPs from state.yml instead of .env
            project_root = get_project_root()
            state_mgr = StateManager(project_root, self.project_name)
            state = state_mgr.load_state()

            click.echo("[DEBUG] preserve_ip=True, loading from state.yml")
            if state and "vms" in state:
                vms = state.get("vms", {})
                click.echo(f"[DEBUG] Found {len(vms)} VMs in state")
                for vm_name, vm_data in vms.items():
                    if "external_ip" in vm_data:
                        existing_ips[vm_name] = vm_data["external_ip"]
                        click.echo(
                            f"[DEBUG] Preserving IP: {vm_name} = {vm_data['external_ip']}"
                        )

                if existing_ips:
                    click.echo(f"[DEBUG] Total IPs to preserve: {len(existing_ips)}")
                else:
                    click.echo("[DEBUG] No IPs found to preserve!")
            else:
                click.echo("[DEBUG] No state found or VMs not deployed yet")

        # Build dynamic vm_groups
        # Format: { "vm-name-index": { role: "...", machine_type: "...", ... } }
        vm_groups = {}

        for vm_role, vm_definition in vms_config.items():
            count = vm_definition.get("count", 1)
            machine_type = vm_definition.get("machine_type", "e2-medium")
            disk_size = vm_definition.get("disk_size", 20)
            services = vm_definition.get("services", [])

            # Create VM instances for this role
            for i in range(count):
                # Generate unique key for each VM instance
                vm_key = f"{vm_role}-{i}"

                # Build labels from services
                labels = {}
                for service in services:
                    labels[f"has_{service}"] = "true"

                # Build tags from role and services (always include ssh for firewall)
                tags = [vm_role, "ssh"] + services

                vm_config = {
                    "role": vm_role,
                    "index": i,
                    "machine_type": machine_type,
                    "disk_size": disk_size,
                    "tags": tags,
                    "labels": labels,
                }

                # Add existing IP if preserve_ip is enabled
                if preserve_ip and vm_key in existing_ips:
                    vm_config["preserve_ip"] = existing_ips[vm_key]

                vm_groups[vm_key] = vm_config

        # Extract app ports from apps configuration
        apps_config = self.raw_config.get("apps", {})
        app_ports = []
        for app_name, app_config in apps_config.items():
            # Support both 'port' and 'external_port'
            port = app_config.get("external_port") or app_config.get("port")
            if port:
                app_ports.append(str(port))

        # Remove duplicates and sort
        app_ports = sorted(list(set(app_ports)))

        # Get orchestrator IP for metrics firewall
        orchestrator_ip = ""
        try:
            from cli.core.orchestrator_loader import OrchestratorLoader

            project_root = (
                self.project_dir.parent.parent
                if self.project_dir.parent.name == "projects"
                else self.project_dir.parent
            )
            orch_loader = OrchestratorLoader(project_root / "shared")
            orch_config = orch_loader.load()
            orchestrator_ip = orch_config.get_ip() or ""
        except:
            pass  # Orchestrator not deployed yet, that's ok

        return {
            "project_id": gcp_config.get("project_id", ""),
            "project_name": self.project_name,
            "region": gcp_config.get("region", "us-central1"),
            "zone": gcp_config.get("zone", "us-central1-a"),
            "vm_groups": vm_groups,
            "subnet_cidr": project_subnet,  # Use allocated subnet instead of config
            "network_name": f"{self.project_name}-network",
            "ssh_pub_key_path": ssh_config.get("public_key_path", "~/.ssh/id_rsa.pub"),
            "app_ports": app_ports,
            "orchestrator_ip": orchestrator_ip,
        }

    def to_ansible_vars(self) -> Dict[str, Any]:
        """
        Convert to Ansible variables format

        Returns:
            Dictionary suitable for Ansible extra vars
        """
        addons = self.get_addons()

        # Get docker configuration from secrets (DOCKER_ORG, DOCKER_USERNAME)
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()
        try:
            result = db.execute(
                text(
                    "SELECT key, value FROM secrets WHERE project_name = :project AND key IN ('DOCKER_ORG', 'DOCKER_USERNAME')"
                ),
                {"project": self.project_name},
            )
            docker_secrets = {row[0]: row[1] for row in result}
            docker_config = {
                "organization": docker_secrets.get("DOCKER_ORG")
                or docker_secrets.get("DOCKER_USERNAME", ""),
                "registry": "docker.io",
            }
        finally:
            db.close()

        return {
            "project_name": self.project_name,
            "project_config": self.raw_config,
            # NOTE: enabled_addons is NOT included here because it's VM-specific
            # It comes from inventory vm_services variable for each host
            "addon_configs": addons,
            "vm_config": self.get_vm_config(),
            "network_config": self.get_network_config(),
            "apps": self.get_apps(),
            "monitoring": self.get_monitoring_config(),
            "docker": docker_config,
        }


class ConfigLoader:
    """Loads and manages project configurations from database"""

    def __init__(self, projects_dir: Path):
        """
        Initialize configuration loader

        Args:
            projects_dir: Path to projects directory (used for backward compat checks)
        """
        self.projects_dir = Path(projects_dir)

    def _load_from_database(self, project_name: str) -> Dict[str, Any]:
        """
        Load project configuration from database.

        Args:
            project_name: Name of the project

        Returns:
            Configuration dictionary in config.yml format

        Raises:
            FileNotFoundError: If project not found in database
        """
        from cli.database import get_db_session
        from sqlalchemy import Table, Column, Integer, String, JSON, DateTime, MetaData

        db = get_db_session()
        try:
            metadata = MetaData()
            projects_table = Table(
                "projects",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("name", String(100)),
                Column("description", String(500)),
                Column("domain", String(200)),
                Column("ssl_email", String(200)),
                Column("github_org", String(100)),
                Column("gcp_project", String(100)),
                Column("gcp_region", String(50)),
                Column("gcp_zone", String(50)),
                Column("ssh_key_path", String(255)),
                Column("ssh_public_key_path", String(255)),
                Column("ssh_user", String(50)),
                Column("docker_registry", String(200)),
                Column("docker_organization", String(100)),
                Column("vpc_subnet", String(50)),
                Column("docker_subnet", String(50)),
                Column("vms", JSON),
                Column("apps_config", JSON),
                Column("addons_config", JSON),
                Column("created_at", DateTime),
                Column("updated_at", DateTime),
            )

            result = db.execute(
                projects_table.select().where(projects_table.c.name == project_name)
            )
            row = result.fetchone()

            if not row:
                raise FileNotFoundError(
                    f"Project '{project_name}' not found in database.\n"
                    f"Run 'superdeploy {project_name}:init' to create it."
                )

            # Convert database row to config.yml-like dict
            config_dict = {
                "project": {
                    "name": row.name,
                    "description": row.description or f"{row.name} project",
                    "created_at": row.created_at.isoformat()
                    if row.created_at
                    else None,
                    "ssl_email": row.ssl_email,
                },
                "cloud": {
                    "gcp": {
                        "project_id": row.gcp_project,
                        "region": row.gcp_region,
                        "zone": row.gcp_zone,
                    },
                    "ssh": {
                        "key_path": row.ssh_key_path,
                        "public_key_path": row.ssh_public_key_path,
                        "user": row.ssh_user,
                    },
                },
                "docker": {
                    "registry": row.docker_registry,
                    "organization": row.docker_organization,
                },
                "github": {
                    "organization": row.github_org,
                },
                "network": {
                    "vpc_subnet": row.vpc_subnet,
                    "docker_subnet": row.docker_subnet,
                },
                "vms": row.vms or {},
                "apps": row.apps_config or {},
                "addons": row.addons_config or {},
            }

            return config_dict

        finally:
            db.close()

    def load_project(self, project_name: str) -> ProjectConfig:
        """
        Load a specific project configuration from database.

        Args:
            project_name: Name of the project to load

        Returns:
            ProjectConfig instance

        Raises:
            FileNotFoundError: If project doesn't exist in database
            ValueError: If configuration is invalid
        """
        # Load from database
        config_dict = self._load_from_database(project_name)

        if not config_dict:
            raise ValueError(f"Empty configuration for project: {project_name}")

        project_dir = self.projects_dir / project_name
        return ProjectConfig(project_name, config_dict, project_dir)

    def list_projects(self) -> List[str]:
        """
        List all available projects from database.

        Returns:
            Sorted list of project names
        """
        from cli.database import get_db_session
        from sqlalchemy import Table, Column, Integer, String, MetaData

        db = get_db_session()
        try:
            metadata = MetaData()
            projects_table = Table(
                "projects",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("name", String(100)),
            )

            result = db.execute(
                projects_table.select().where(projects_table.c.name != "orchestrator")
            )
            projects = [row.name for row in result.fetchall()]
            return sorted(projects)

        finally:
            db.close()

    def project_exists(self, project_name: str) -> bool:
        """
        Check if a project exists in database.

        Args:
            project_name: Name of the project to check

        Returns:
            True if project exists, False otherwise
        """
        try:
            self._load_from_database(project_name)
            return True
        except FileNotFoundError:
            return False
