"""Configuration management for SuperDeploy projects"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List
import yaml


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


class ProjectConfig:
    """Represents a loaded and validated project configuration"""

    def __init__(self, project_name: str, config_dict: dict, project_dir: Path = None):
        """
        Initialize project configuration

        Args:
            project_name: Name of the project
            config_dict: Raw configuration dictionary from project.yml
            project_dir: Path to project directory (optional)
        """
        self.project_name = project_name
        self.raw_config = config_dict
        self.project_dir = project_dir
        self.config_path = project_dir / "project.yml" if project_dir else None
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
        """Save configuration back to yaml file"""
        if not self.config_path or not self.config_path.exists():
            return

        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.raw_config, f, default_flow_style=False, sort_keys=False)
        except Exception:
            # Silently fail - not critical
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
        Get application configurations

        Returns:
            Dictionary of application configurations
        """
        return self.raw_config.get("apps", {})

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

        Dynamically builds vm_groups from project.yml vms section.
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
        }


class ConfigLoader:
    """Loads and manages project configurations"""

    def __init__(self, projects_dir: Path):
        """
        Initialize configuration loader

        Args:
            projects_dir: Path to projects directory
        """
        self.projects_dir = Path(projects_dir)

    def load_project(self, project_name: str) -> ProjectConfig:
        """
        Load a specific project configuration

        Args:
            project_name: Name of the project to load

        Returns:
            ProjectConfig instance

        Raises:
            FileNotFoundError: If project config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_file = self.projects_dir / project_name / "project.yml"

        if not config_file.exists():
            raise FileNotFoundError(
                f"Project configuration not found: {config_file}\n"
                f"Run 'superdeploy init -p {project_name}' to create it."
            )

        with open(config_file, "r") as f:
            config_dict = yaml.safe_load(f)

        if not config_dict:
            raise ValueError(f"Empty or invalid configuration file: {config_file}")

        project_dir = self.projects_dir / project_name
        return ProjectConfig(project_name, config_dict, project_dir)

    def list_projects(self) -> List[str]:
        """
        List all available projects

        Returns:
            Sorted list of project names
        """
        if not self.projects_dir.exists():
            return []

        projects = []
        for item in self.projects_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                config_file = item / "project.yml"
                if config_file.exists():
                    projects.append(item.name)

        return sorted(projects)

    def project_exists(self, project_name: str) -> bool:
        """
        Check if a project exists

        Args:
            project_name: Name of the project to check

        Returns:
            True if project exists, False otherwise
        """
        config_file = self.projects_dir / project_name / "project.yml"
        return config_file.exists()
