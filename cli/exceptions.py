"""
SuperDeploy CLI Exception Hierarchy

Clean exception hierarchy for consistent error handling across the CLI.
"""

from typing import Optional


class SuperDeployError(Exception):
    """Base exception for all SuperDeploy errors."""

    def __init__(self, message: str, context: Optional[str] = None):
        self.message = message
        self.context = context
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message with optional context."""
        if self.context:
            return f"{self.message}\nContext: {self.context}"
        return self.message


class ConfigurationError(SuperDeployError):
    """Raised when configuration is invalid or missing."""

    pass


class DeploymentError(SuperDeployError):
    """Raised when deployment operations fail."""

    pass


class ValidationError(SuperDeployError):
    """Raised when validation fails."""

    pass


class InfrastructureError(SuperDeployError):
    """Raised when infrastructure provisioning fails."""

    pass


class StateError(SuperDeployError):
    """Raised when state management operations fail."""

    pass


class SecretError(SuperDeployError):
    """Raised when secret operations fail."""

    pass


class SSHError(SuperDeployError):
    """Raised when SSH operations fail."""

    pass


class TerraformError(SuperDeployError):
    """Raised when Terraform operations fail."""

    pass


class AppNotFoundError(ConfigurationError):
    """Raised when app does not exist in project."""

    def __init__(self, app_name: str, project_name: str, available_apps: list[str]):
        self.app_name = app_name
        self.project_name = project_name
        self.available_apps = available_apps
        message = f"App '{app_name}' not found in project '{project_name}'"
        context = f"Available apps: {', '.join(available_apps)}"
        super().__init__(message, context)


class VMNotFoundError(InfrastructureError):
    """Raised when VM does not exist."""

    def __init__(self, vm_name: str, available_vms: list[str]):
        self.vm_name = vm_name
        self.available_vms = available_vms
        message = f"VM '{vm_name}' not found"
        context = f"Available VMs: {', '.join(available_vms)}"
        super().__init__(message, context)


class ProjectNotDeployedError(DeploymentError):
    """Raised when attempting operations on undeployed project."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        message = f"Project '{project_name}' is not deployed"
        context = f"Run: superdeploy {project_name}:up"
        super().__init__(message, context)
