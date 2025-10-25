"""Validation engine for detecting conflicts and compatibility issues"""

from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import yaml
import ipaddress

from .addon import Addon


class ValidationError:
    """Represents a validation error with type, message, and severity"""
    
    def __init__(self, error_type: str, message: str, severity: str = 'error'):
        """
        Initialize a validation error.
        
        Args:
            error_type: Type of error (subnet_conflict, port_conflict, etc.)
            message: Human-readable error message
            severity: Error severity ('error' or 'warning')
        """
        self.type = error_type
        self.message = message
        self.severity = severity
    
    def __str__(self):
        """Format error for display"""
        icon = '❌' if self.severity == 'error' else '⚠️'
        return f"{icon} {self.message}"
    
    def __repr__(self):
        return f"ValidationError(type={self.type}, severity={self.severity}, message={self.message})"


class ValidationException(Exception):
    """Raised when validation fails with one or more errors"""
    
    def __init__(self, errors: List[ValidationError]):
        """
        Initialize validation exception.
        
        Args:
            errors: List of validation errors
        """
        self.errors = errors
        super().__init__(self._format_errors())
    
    def _format_errors(self) -> str:
        """Format all errors for display"""
        lines = ["Validation failed with the following errors:"]
        for error in self.errors:
            lines.append(f"  • {error}")
        return "\n".join(lines)


class ValidationEngine:
    """Validates project configuration for conflicts and compatibility issues"""
    
    def __init__(self, projects_dir: Path):
        """
        Initialize the validation engine.
        
        Args:
            projects_dir: Path to the projects directory
        """
        self.projects_dir = Path(projects_dir)
    
    def validate(
        self, 
        project_config: dict, 
        addons: Dict[str, Addon],
        project_name: Optional[str] = None,
        available_addons: Optional[Set[str]] = None
    ) -> List[ValidationError]:
        """
        Run all validation checks on a project configuration.
        
        Args:
            project_config: Project configuration dictionary
            addons: Dictionary of loaded addons
            project_name: Optional project name (uses config if not provided)
            available_addons: Optional set of available addon names for validation
            
        Returns:
            List of validation errors (empty if validation passes)
        """
        errors = []
        
        # Get project name
        if project_name is None:
            project_name = project_config.get('project', '')
        
        # Ensure project_name is a string
        if not isinstance(project_name, str):
            project_name = str(project_name) if project_name else ''
        
        # Run all validation checks
        errors.extend(self._validate_infrastructure_config(project_config))
        errors.extend(self._validate_vm_config(project_config))
        errors.extend(self._validate_addon_names(project_config, available_addons))
        errors.extend(self._validate_addon_configs(project_config))
        errors.extend(self._validate_subnet_conflicts(project_config, project_name))
        errors.extend(self._validate_port_conflicts(project_config, project_name))
        errors.extend(self._validate_ip_conflicts(project_config))
        errors.extend(self._validate_addon_dependencies(addons))
        errors.extend(self._validate_addon_conflicts(addons))
        
        return errors
    
    def validate_and_raise(
        self,
        project_config: dict,
        addons: Dict[str, Addon],
        project_name: Optional[str] = None,
        available_addons: Optional[Set[str]] = None
    ):
        """
        Validate and raise exception if errors are found.
        
        Args:
            project_config: Project configuration dictionary
            addons: Dictionary of loaded addons
            project_name: Optional project name
            available_addons: Optional set of available addon names for validation
            
        Raises:
            ValidationException: If validation errors are found
        """
        errors = self.validate(project_config, addons, project_name, available_addons)
        
        if errors:
            raise ValidationException(errors)
    
    def _validate_infrastructure_config(
        self,
        project_config: dict
    ) -> List[ValidationError]:
        """
        Validate infrastructure configuration (Forgejo).
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get infrastructure config
        infrastructure = project_config.get('infrastructure', {})
        
        if not isinstance(infrastructure, dict):
            errors.append(ValidationError(
                error_type='invalid_config',
                message="'infrastructure' must be a dictionary"
            ))
            return errors
        
        # Validate Forgejo configuration (required)
        forgejo_config = infrastructure.get('forgejo', {})
        
        if not forgejo_config:
            errors.append(ValidationError(
                error_type='missing_forgejo_config',
                message="'infrastructure.forgejo' configuration is required"
            ))
            return errors
        
        if not isinstance(forgejo_config, dict):
            errors.append(ValidationError(
                error_type='invalid_config',
                message="'infrastructure.forgejo' must be a dictionary"
            ))
            return errors
        
        # Validate required Forgejo fields
        required_fields = ['port', 'ssh_port', 'admin_user', 'org', 'repo']
        for field in required_fields:
            if field not in forgejo_config:
                errors.append(ValidationError(
                    error_type='missing_forgejo_field',
                    message=f"'infrastructure.forgejo.{field}' is required"
                ))
        
        # Validate port numbers
        for port_field in ['port', 'ssh_port']:
            if port_field in forgejo_config:
                port_value = forgejo_config[port_field]
                try:
                    port_int = int(port_value)
                    if port_int < 1 or port_int > 65535:
                        errors.append(ValidationError(
                            error_type='invalid_port',
                            message=(
                                f"'infrastructure.forgejo.{port_field}' must be "
                                f"between 1 and 65535, got {port_int}"
                            )
                        ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        error_type='invalid_port',
                        message=(
                            f"'infrastructure.forgejo.{port_field}' must be a valid "
                            f"port number, got '{port_value}'"
                        )
                    ))
        
        # Validate string fields are not empty
        for string_field in ['admin_user', 'org', 'repo']:
            if string_field in forgejo_config:
                value = forgejo_config[string_field]
                if not value or not str(value).strip():
                    errors.append(ValidationError(
                        error_type='invalid_forgejo_field',
                        message=f"'infrastructure.forgejo.{string_field}' cannot be empty"
                    ))
        
        return errors
    
    def _validate_vm_config(
        self,
        project_config: dict
    ) -> List[ValidationError]:
        """
        Validate VM configuration in infrastructure section.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get infrastructure config
        infrastructure = project_config.get('infrastructure', {})
        
        if not isinstance(infrastructure, dict):
            # Already validated in _validate_infrastructure_config
            return errors
        
        # Get vm_config (optional, but validate if present)
        vm_config = infrastructure.get('vm_config')
        
        # If vm_config is not present, that's okay (defaults will be used)
        if vm_config is None:
            return errors
        
        if not isinstance(vm_config, dict):
            errors.append(ValidationError(
                error_type='invalid_vm_config',
                message="'infrastructure.vm_config' must be a dictionary"
            ))
            return errors
        
        # Validate machine_type (if present)
        if 'machine_type' in vm_config:
            machine_type = vm_config['machine_type']
            if not machine_type or not isinstance(machine_type, str) or not machine_type.strip():
                errors.append(ValidationError(
                    error_type='invalid_machine_type',
                    message="'infrastructure.vm_config.machine_type' must be a non-empty string"
                ))
            else:
                # Basic validation - machine type should match common patterns
                machine_type_str = str(machine_type).strip()
                if not machine_type_str:
                    errors.append(ValidationError(
                        error_type='invalid_machine_type',
                        message="'infrastructure.vm_config.machine_type' cannot be empty"
                    ))
        
        # Validate disk_size (if present)
        if 'disk_size' in vm_config:
            disk_size = vm_config['disk_size']
            try:
                disk_size_int = int(disk_size)
                if disk_size_int < 10:
                    errors.append(ValidationError(
                        error_type='invalid_disk_size',
                        message=(
                            f"'infrastructure.vm_config.disk_size' must be at least 10 GB, "
                            f"got {disk_size_int}"
                        )
                    ))
                elif disk_size_int > 10000:
                    errors.append(ValidationError(
                        error_type='invalid_disk_size',
                        message=(
                            f"'infrastructure.vm_config.disk_size' must be at most 10000 GB, "
                            f"got {disk_size_int}"
                        ),
                        severity='warning'
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    error_type='invalid_disk_size',
                    message=(
                        f"'infrastructure.vm_config.disk_size' must be a valid integer, "
                        f"got '{disk_size}'"
                    )
                ))
        
        # Validate image (if present)
        if 'image' in vm_config:
            image = vm_config['image']
            if not image or not isinstance(image, str) or not image.strip():
                errors.append(ValidationError(
                    error_type='invalid_image',
                    message="'infrastructure.vm_config.image' must be a non-empty string"
                ))
            else:
                # Basic validation - image should contain a slash (project/image format)
                image_str = str(image).strip()
                if '/' not in image_str:
                    errors.append(ValidationError(
                        error_type='invalid_image',
                        message=(
                            f"'infrastructure.vm_config.image' should be in format "
                            f"'project/image', got '{image_str}'"
                        ),
                        severity='warning'
                    ))
        
        return errors
    
    def _validate_addon_names(
        self,
        project_config: dict,
        available_addons: Optional[Set[str]] = None
    ) -> List[ValidationError]:
        """
        Validate that all addon names in project config are valid.
        
        Args:
            project_config: Project configuration dictionary
            available_addons: Optional set of available addon names
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # If no available addons provided, skip validation
        if available_addons is None:
            return errors
        
        # Get core services from config
        core_services = project_config.get('core_services', {})
        
        if not isinstance(core_services, dict):
            errors.append(ValidationError(
                error_type='invalid_config',
                message="'core_services' must be a dictionary"
            ))
            return errors
        
        # Check each addon name
        for addon_name in core_services.keys():
            if addon_name not in available_addons:
                errors.append(ValidationError(
                    error_type='invalid_addon',
                    message=(
                        f"Unknown addon '{addon_name}'. "
                        f"Available addons: {', '.join(sorted(available_addons))}"
                    )
                ))
        
        return errors
    
    def _validate_addon_configs(
        self,
        project_config: dict
    ) -> List[ValidationError]:
        """
        Validate addon configurations in core_services.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get core services from config
        core_services = project_config.get('core_services', {})
        
        if not isinstance(core_services, dict):
            # Already validated in _validate_addon_names
            return errors
        
        # Validate each addon configuration
        for addon_name, addon_config in core_services.items():
            if addon_config is None:
                # Addon enabled with no custom config is valid
                continue
            
            if not isinstance(addon_config, dict):
                errors.append(ValidationError(
                    error_type='invalid_addon_config',
                    message=(
                        f"Configuration for addon '{addon_name}' must be a dictionary, "
                        f"got {type(addon_config).__name__}"
                    )
                ))
                continue
            
            # Validate port if specified
            if 'port' in addon_config:
                port_value = addon_config['port']
                try:
                    port_int = int(port_value)
                    if port_int < 1 or port_int > 65535:
                        errors.append(ValidationError(
                            error_type='invalid_port',
                            message=(
                                f"Port for addon '{addon_name}' must be between 1 and 65535, "
                                f"got {port_int}"
                            )
                        ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        error_type='invalid_port',
                        message=(
                            f"Port for addon '{addon_name}' must be a valid port number, "
                            f"got '{port_value}'"
                        )
                    ))
        
        return errors
    
    def _validate_subnet_conflicts(
        self, 
        project_config: dict,
        project_name: str
    ) -> List[ValidationError]:
        """
        Check for subnet conflicts across all projects.
        
        Args:
            project_config: Project configuration dictionary
            project_name: Name of the project being validated
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get subnet from project config
        subnet_str = project_config.get('network', {}).get('subnet')
        
        if not subnet_str:
            errors.append(ValidationError(
                error_type='missing_subnet',
                message=f"Project '{project_name}' is missing network.subnet configuration"
            ))
            return errors
        
        # Validate subnet format
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
        except ValueError as e:
            errors.append(ValidationError(
                error_type='invalid_subnet',
                message=f"Project '{project_name}' has invalid subnet '{subnet_str}': {e}"
            ))
            return errors
        
        # Get all existing subnets
        used_subnets = self._get_used_subnets()
        
        # Check for conflicts
        for existing_subnet_str, existing_project in used_subnets.items():
            # Skip if it's the same project (updating existing project)
            if existing_project == project_name:
                continue
            
            try:
                existing_subnet = ipaddress.ip_network(existing_subnet_str, strict=False)
                
                # Check if subnets overlap
                if subnet.overlaps(existing_subnet):
                    errors.append(ValidationError(
                        error_type='subnet_conflict',
                        message=(
                            f"Subnet {subnet_str} conflicts with project '{existing_project}' "
                            f"subnet {existing_subnet_str}"
                        )
                    ))
            except ValueError:
                # Skip invalid subnets in existing projects
                continue
        
        return errors
    
    def _validate_port_conflicts(
        self,
        project_config: dict,
        project_name: str
    ) -> List[ValidationError]:
        """
        Check for port conflicts on the same host.
        
        Args:
            project_config: Project configuration dictionary
            project_name: Name of the project being validated
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get all ports used by this project
        project_ports = self._get_project_ports(project_config)
        
        # Get all ports used by other projects
        used_ports = self._get_used_ports()
        
        # Check for conflicts
        for port, app_name in project_ports.items():
            if port in used_ports:
                existing_project, existing_app = used_ports[port]
                
                # Skip if it's the same project (updating existing project)
                if existing_project == project_name:
                    continue
                
                errors.append(ValidationError(
                    error_type='port_conflict',
                    message=(
                        f"Port {port} (used by app '{app_name}') conflicts with "
                        f"project '{existing_project}' app '{existing_app}'"
                    )
                ))
        
        return errors
    
    def _validate_ip_conflicts(self, project_config: dict) -> List[ValidationError]:
        """
        Check for IP address conflicts within project networks.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get subnet
        subnet_str = project_config.get('network', {}).get('subnet')
        
        if not subnet_str:
            return errors  # Already caught by subnet validation
        
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
        except ValueError:
            return errors  # Already caught by subnet validation
        
        # Collect all IP addresses used in the project
        used_ips: Dict[str, str] = {}
        
        # Check VMs for explicit IP assignments
        vms = project_config.get('vms', {})
        for vm_name, vm_config in vms.items():
            if isinstance(vm_config, dict):
                ip_str = vm_config.get('ip')
                if ip_str:
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        
                        # Check if IP is in subnet
                        if ip not in subnet:
                            errors.append(ValidationError(
                                error_type='ip_out_of_subnet',
                                message=(
                                    f"VM '{vm_name}' IP {ip_str} is not in "
                                    f"project subnet {subnet_str}"
                                )
                            ))
                        
                        # Check for duplicate IPs
                        if ip_str in used_ips:
                            errors.append(ValidationError(
                                error_type='ip_conflict',
                                message=(
                                    f"IP address {ip_str} is used by both "
                                    f"'{used_ips[ip_str]}' and '{vm_name}'"
                                )
                            ))
                        else:
                            used_ips[ip_str] = vm_name
                    
                    except ValueError as e:
                        errors.append(ValidationError(
                            error_type='invalid_ip',
                            message=f"VM '{vm_name}' has invalid IP address '{ip_str}': {e}"
                        ))
        
        # Check apps for explicit IP assignments
        apps = project_config.get('apps', {})
        for app_name, app_config in apps.items():
            if isinstance(app_config, dict):
                ip_str = app_config.get('ip')
                if ip_str:
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        
                        # Check if IP is in subnet
                        if ip not in subnet:
                            errors.append(ValidationError(
                                error_type='ip_out_of_subnet',
                                message=(
                                    f"App '{app_name}' IP {ip_str} is not in "
                                    f"project subnet {subnet_str}"
                                )
                            ))
                        
                        # Check for duplicate IPs
                        if ip_str in used_ips:
                            errors.append(ValidationError(
                                error_type='ip_conflict',
                                message=(
                                    f"IP address {ip_str} is used by both "
                                    f"'{used_ips[ip_str]}' and '{app_name}'"
                                )
                            ))
                        else:
                            used_ips[ip_str] = app_name
                    
                    except ValueError as e:
                        errors.append(ValidationError(
                            error_type='invalid_ip',
                            message=f"App '{app_name}' has invalid IP address '{ip_str}': {e}"
                        ))
        
        return errors
    
    def _validate_addon_dependencies(self, addons: Dict[str, Addon]) -> List[ValidationError]:
        """
        Check that all addon dependencies are satisfied.
        
        Args:
            addons: Dictionary of loaded addons
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for addon_name, addon in addons.items():
            dependencies = addon.get_dependencies()
            
            for required_addon in dependencies:
                if required_addon not in addons:
                    errors.append(ValidationError(
                        error_type='missing_dependency',
                        message=(
                            f"Addon '{addon_name}' requires addon '{required_addon}' "
                            f"but it is not enabled in the project configuration"
                        )
                    ))
        
        return errors
    
    def _validate_addon_conflicts(self, addons: Dict[str, Addon]) -> List[ValidationError]:
        """
        Check for conflicting addons.
        
        Args:
            addons: Dictionary of loaded addons
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for addon_name, addon in addons.items():
            conflicts = addon.get_conflicts()
            
            for conflicting_addon in conflicts:
                if conflicting_addon in addons:
                    errors.append(ValidationError(
                        error_type='addon_conflict',
                        message=(
                            f"Addon '{addon_name}' conflicts with addon '{conflicting_addon}'. "
                            f"These addons cannot be used together in the same project"
                        )
                    ))
        
        return errors
    
    def _get_used_subnets(self) -> Dict[str, str]:
        """
        Get all subnets in use by existing projects.
        
        Returns:
            Dictionary mapping subnet strings to project names
        """
        used = {}
        
        if not self.projects_dir.exists():
            return used
        
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith('.'):
                continue
            
            config_file = project_dir / "project.yml"
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    if config:
                        subnet = config.get('network', {}).get('subnet')
                        project_name = config.get('project', project_dir.name)
                        
                        if subnet:
                            used[subnet] = project_name
                
                except (yaml.YAMLError, IOError):
                    # Skip projects with invalid config files
                    continue
        
        return used
    
    def _get_used_ports(self) -> Dict[int, Tuple[str, str]]:
        """
        Get all ports in use across all projects.
        
        Returns:
            Dictionary mapping port numbers to (project_name, app_name) tuples
        """
        used = {}
        
        if not self.projects_dir.exists():
            return used
        
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith('.'):
                continue
            
            config_file = project_dir / "project.yml"
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    if config:
                        project_name = config.get('project', project_dir.name)
                        apps = config.get('apps', {})
                        
                        for app_name, app_config in apps.items():
                            if isinstance(app_config, dict):
                                port = app_config.get('port')
                                if port:
                                    try:
                                        port_int = int(port)
                                        used[port_int] = (project_name, app_name)
                                    except (ValueError, TypeError):
                                        # Skip invalid port values
                                        continue
                
                except (yaml.YAMLError, IOError):
                    # Skip projects with invalid config files
                    continue
        
        return used
    
    def _get_project_ports(self, project_config: dict) -> Dict[int, str]:
        """
        Get all ports used by a project.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            Dictionary mapping port numbers to app/service names
        """
        ports = {}
        
        # Get Forgejo ports from infrastructure config
        infrastructure = project_config.get('infrastructure', {})
        if isinstance(infrastructure, dict):
            forgejo_config = infrastructure.get('forgejo', {})
            if isinstance(forgejo_config, dict):
                # Forgejo web port
                forgejo_port = forgejo_config.get('port')
                if forgejo_port:
                    try:
                        port_int = int(forgejo_port)
                        ports[port_int] = 'forgejo (web)'
                    except (ValueError, TypeError):
                        pass
                
                # Forgejo SSH port
                forgejo_ssh_port = forgejo_config.get('ssh_port')
                if forgejo_ssh_port:
                    try:
                        port_int = int(forgejo_ssh_port)
                        ports[port_int] = 'forgejo (ssh)'
                    except (ValueError, TypeError):
                        pass
        
        # Get addon ports from core_services
        core_services = project_config.get('core_services', {})
        if isinstance(core_services, dict):
            for addon_name, addon_config in core_services.items():
                if isinstance(addon_config, dict):
                    port = addon_config.get('port')
                    if port:
                        try:
                            port_int = int(port)
                            ports[port_int] = f'{addon_name} (addon)'
                        except (ValueError, TypeError):
                            continue
        
        # Get app ports
        apps = project_config.get('apps', {})
        for app_name, app_config in apps.items():
            if isinstance(app_config, dict):
                port = app_config.get('port')
                if port:
                    try:
                        port_int = int(port)
                        ports[port_int] = f'{app_name} (app)'
                    except (ValueError, TypeError):
                        # Skip invalid port values
                        continue
        
        return ports
