"""Configuration management for SuperDeploy projects"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
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
    subnet: str = "172.20.0.0/24"


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
        # Ensure infrastructure section exists
        if 'infrastructure' not in self.raw_config:
            self.raw_config['infrastructure'] = {}
        
        # Ensure vm_config section exists with defaults
        if 'vm_config' not in self.raw_config['infrastructure']:
            self.raw_config['infrastructure']['vm_config'] = {}
        
        vm_config = self.raw_config['infrastructure']['vm_config']
        if 'machine_type' not in vm_config:
            vm_config['machine_type'] = 'e2-medium'
        if 'disk_size' not in vm_config:
            vm_config['disk_size'] = 20
        if 'image' not in vm_config:
            vm_config['image'] = 'debian-cloud/debian-11'
        
        # Ensure network section exists with defaults
        if 'network' not in self.raw_config:
            self.raw_config['network'] = {}
        if 'subnet' not in self.raw_config['network']:
            self.raw_config['network']['subnet'] = '172.20.0.0/24'
        
        # Ensure monitoring section exists with defaults
        if 'monitoring' not in self.raw_config:
            self.raw_config['monitoring'] = {}
        if 'enabled' not in self.raw_config['monitoring']:
            self.raw_config['monitoring']['enabled'] = True
    
    def _validate(self) -> None:
        """Validate configuration"""
        # Validate required fields
        if 'project' not in self.raw_config:
            raise ValueError("Missing required field: 'project'")
        
        # Validate project name matches
        if self.raw_config['project'] != self.project_name:
            raise ValueError(
                f"Project name mismatch: config has '{self.raw_config['project']}' "
                f"but expected '{self.project_name}'"
            )
        
        # Validate VM config values
        vm_config = self.get_vm_config()
        if vm_config['disk_size'] <= 0:
            raise ValueError(f"Invalid disk_size: {vm_config['disk_size']} (must be > 0)")
        
        # Validate network subnet format (basic check)
        subnet = self.get_network_config().get('subnet', '')
        if '/' not in subnet:
            raise ValueError(f"Invalid subnet format: {subnet} (expected CIDR notation)")
    
    def get_vm_config(self) -> Dict[str, Any]:
        """
        Get VM configuration with defaults
        
        Returns:
            Dictionary with machine_type, disk_size, and image
        """
        vm_config = self.raw_config.get('infrastructure', {}).get('vm_config', {})
        return {
            'machine_type': vm_config.get('machine_type', 'e2-medium'),
            'disk_size': vm_config.get('disk_size', 20),
            'image': vm_config.get('image', 'debian-cloud/debian-11')
        }
    
    def get_network_config(self) -> Dict[str, Any]:
        """
        Get network configuration
        
        Returns:
            Dictionary with network settings
        """
        return self.raw_config.get('network', {})
    
    def get_apps(self) -> Dict[str, Dict[str, Any]]:
        """
        Get application configurations
        
        Returns:
            Dictionary of application configurations
        """
        return self.raw_config.get('apps', {})
    
    def get_core_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Get core services configuration
        
        Returns:
            Dictionary of core service configurations
        """
        return self.raw_config.get('core_services', {})
    
    def get_infrastructure(self) -> Dict[str, Any]:
        """
        Get infrastructure configuration
        
        Returns:
            Dictionary with infrastructure settings
        """
        return self.raw_config.get('infrastructure', {})
    
    def get_vms(self) -> Dict[str, Dict[str, Any]]:
        """
        Get VM definitions
        
        Returns:
            Dictionary of VM configurations
        """
        return self.raw_config.get('vms', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """
        Get monitoring configuration
        
        Returns:
            Dictionary with monitoring settings
        """
        return self.raw_config.get('monitoring', {})
    
    def get_enabled_addons(self) -> List[str]:
        """
        Get list of enabled addons from infrastructure and core_services
        
        Returns:
            List of enabled addon names
        """
        enabled_addons = []
        
        # Add addons from infrastructure section (e.g., forgejo)
        infrastructure = self.raw_config.get('infrastructure', {})
        for key in infrastructure.keys():
            if key != 'vm_config':  # Skip vm_config, it's not an addon
                enabled_addons.append(key)
        
        # Add addons from core_services section (e.g., postgres, rabbitmq)
        core_services = self.raw_config.get('core_services', {})
        enabled_addons.extend(list(core_services.keys()))
        
        return enabled_addons
    
    def get_addon_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get addon configurations from both infrastructure and core_services
        
        Returns:
            Dictionary of addon configurations
        """
        addon_configs = {}
        
        # Add configs from infrastructure
        infrastructure = self.raw_config.get('infrastructure', {})
        for key, value in infrastructure.items():
            if key != 'vm_config' and isinstance(value, dict):
                addon_configs[key] = value
        
        # Add configs from core_services
        core_services = self.raw_config.get('core_services', {})
        addon_configs.update(core_services)
        
        return addon_configs
    
    def to_terraform_vars(self) -> Dict[str, Any]:
        """
        Convert to Terraform variables format
        
        Returns:
            Dictionary suitable for Terraform tfvars
        """
        vm_config = self.get_vm_config()
        network_config = self.get_network_config()
        
        return {
            'project_name': self.project_name,
            'machine_type': vm_config['machine_type'],
            'disk_size': vm_config['disk_size'],
            'vm_image': vm_config['image'],
            'subnet_cidr': network_config.get('subnet', '172.20.0.0/24')
        }
    
    def to_ansible_vars(self) -> Dict[str, Any]:
        """
        Convert to Ansible variables format
        
        Returns:
            Dictionary suitable for Ansible extra vars
        """
        return {
            'project_name': self.project_name,
            'project_config': self.raw_config,
            'enabled_addons': self.get_enabled_addons(),
            'addon_configs': self.get_addon_configs(),
            'vm_config': self.get_vm_config(),
            'network_config': self.get_network_config(),
            'apps': self.get_apps(),
            'core_services': self.get_core_services(),
            'infrastructure': self.get_infrastructure(),
            'monitoring': self.get_monitoring_config()
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
        
        with open(config_file, 'r') as f:
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
            if item.is_dir() and not item.name.startswith('.'):
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
