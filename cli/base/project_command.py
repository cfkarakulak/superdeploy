"""
Project Command Base Class

Base class for project-specific commands.
Provides automatic service initialization.
"""

from typing import Optional
from .base_command import BaseCommand
from cli.services import (
    StateService,
    ConfigService,
    SecretService,
    VMService,
)


class ProjectCommand(BaseCommand):
    """
    Base class for project-specific commands.

    Provides:
    - Automatic service initialization
    - Project validation
    - Pre-configured state, config, secret access
    """

    def __init__(self, project_name: str, verbose: bool = False, json_output: bool = False):
        super().__init__(verbose=verbose, json_output=json_output)
        self.project_name = project_name

        # Initialize services
        self.config_service = ConfigService(self.project_root)
        self.state_service: Optional[StateService] = None
        self.secret_service: Optional[SecretService] = None
        self.vm_service: Optional[VMService] = None

    def validate_project(self) -> None:
        """
        Validate that project exists and has valid config.

        Raises:
            SystemExit: If project invalid
        """
        try:
            self.config_service.validate_project(self.project_name)
        except FileNotFoundError as e:
            self.exit_with_error(str(e))
        except ValueError as e:
            self.exit_with_error(f"Invalid project configuration: {e}")

    def ensure_state_service(self) -> StateService:
        """
        Ensure StateService is initialized.

        Returns:
            StateService instance
        """
        if self.state_service is None:
            self.state_service = StateService(self.project_root, self.project_name)
        return self.state_service

    def ensure_vm_service(self) -> VMService:
        """
        Ensure VMService is initialized.

        Returns:
            VMService instance
        """
        if self.vm_service is None:
            self.vm_service = VMService(self.project_root, self.project_name)
        return self.vm_service

    def require_deployment(self) -> None:
        """
        Ensure project is deployed (has state).

        Raises:
            SystemExit: If not deployed
        """
        state_service = self.ensure_state_service()

        if not state_service.has_state():
            self.exit_with_error(
                f"Project '{self.project_name}' not deployed\n"
                f"Run: superdeploy {self.project_name}:up"
            )

    def get_app_config(self, app_name: str) -> dict:
        """
        Get app configuration.

        Args:
            app_name: App name

        Returns:
            App config dict
        """
        try:
            return self.config_service.get_app_config(self.project_name, app_name)
        except KeyError as e:
            self.exit_with_error(str(e))

    def get_vm_for_app(self, app_name: str) -> tuple[str, str]:
        """
        Get VM name and IP for app.

        Args:
            app_name: App name

        Returns:
            Tuple of (vm_name, vm_ip)
        """
        vm_service = self.ensure_vm_service()
        return vm_service.get_vm_for_app(app_name)

    def get_ssh_config(self) -> dict:
        """
        Get SSH configuration for project.

        Returns:
            SSH config dict
        """
        return self.config_service.get_ssh_config(self.project_name)

    def list_apps(self) -> list[str]:
        """
        List all apps in project.

        Returns:
            List of app names
        """
        return self.config_service.list_apps(self.project_name)

    def run(self, **kwargs) -> None:
        """
        Run command with project validation.

        Args:
            **kwargs: Command arguments
        """
        # Validate project first
        self.validate_project()

        # Then run normal execution
        super().run(**kwargs)
