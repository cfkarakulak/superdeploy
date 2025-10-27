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

    def __init__(self, project_name: str, config_dict: dict):
        """
        Initialize project configuration

        Args:
            project_name: Name of the project
            config_dict: Raw configuration dictionary from project.yml
        """
        self.project_name = project_name
        self.raw_config = config_dict
        self._apply_defaults()
        self._validate()

    def _apply_defaults(self) -> None:
        """Apply default values to configuration"""
        # Ensure network section exists with defaults
        if "network" not in self.raw_config:
            self.raw_config["network"] = {}
        if "vpc_subnet" not in self.raw_config["network"]:
            self.raw_config["network"]["vpc_subnet"] = "10.128.0.0/20"
        if "docker_subnet" not in self.raw_config["network"]:
            self.raw_config["network"]["docker_subnet"] = "172.30.0.0/24"

        # Ensure monitoring section exists with defaults
        if "monitoring" not in self.raw_config:
            self.raw_config["monitoring"] = {}
        if "enabled" not in self.raw_config["monitoring"]:
            self.raw_config["monitoring"]["enabled"] = True

    def _validate(self) -> None:
        """Validate configuration"""
        # Validate required fields
        if "project" not in self.raw_config:
            raise ValueError("Missing required field: 'project'")

        # Validate project name matches
        if self.raw_config["project"] != self.project_name:
            raise ValueError(
                f"Project name mismatch: config has '{self.raw_config['project']}' "
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
        Get monitoring configuration

        Returns:
            Dictionary with monitoring settings
        """
        return self.raw_config.get("monitoring", {})

    def get_addons(self) -> Dict[str, Dict[str, Any]]:
        """
        Get addon configurations from addons section.
        
        Returns:
            Dictionary of addon configurations
        """
        return self.raw_config.get('addons', {})

    def to_terraform_vars(self) -> Dict[str, Any]:
        """
        Convert to Terraform variables format

        Dynamically builds vm_groups from project.yml vms section.
        Each VM is created with all its properties.

        Returns:
            Dictionary suitable for Terraform tfvars
        """
        network_config = self.get_network_config()
        vms_config = self.get_vms()
        cloud_config = self.raw_config.get("cloud", {})
        gcp_config = cloud_config.get("gcp", {})
        ssh_config = cloud_config.get("ssh", {})

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

                vm_groups[vm_key] = {
                    "role": vm_role,
                    "index": i,
                    "machine_type": machine_type,
                    "disk_size": disk_size,
                    "tags": tags,
                    "labels": labels,
                }

        return {
            "project_id": gcp_config.get("project_id", ""),
            "project_name": self.project_name,
            "region": gcp_config.get("region", "us-central1"),
            "zone": gcp_config.get("zone", "us-central1-a"),
            "vm_groups": vm_groups,
            "subnet_cidr": network_config.get("vpc_subnet", "10.128.0.0/20"),
            "network_name": f"{self.project_name}-network",
            "ssh_pub_key_path": ssh_config.get("public_key_path", "~/.ssh/id_rsa.pub"),
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
            "enabled_addons": list(addons.keys()),
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

        return ProjectConfig(project_name, config_dict)

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
