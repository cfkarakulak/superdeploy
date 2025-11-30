"""
VM Management Service

Centralized VM queries, IP resolution, and status checks with type-safe models.
"""

from pathlib import Path
from typing import Dict, Tuple, Optional

from .state_service import StateService
from .config_service import ConfigService
from .ssh_service import SSHService
from cli.models.deployment import VMState
from cli.models.ssh import SSHConfig
from cli.exceptions import VMNotFoundError, AppNotFoundError


class VMService:
    """
    Centralized VM management service.

    Responsibilities:
    - VM IP resolution
    - VM-to-app mapping
    - VM health checks
    - Combined state + config queries
    """

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize VM service.

        Args:
            project_root: Path to superdeploy root directory
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.state_service = StateService(project_root, project_name)
        self.config_service = ConfigService(project_root)

    def get_vm_state(self, vm_name: str) -> VMState:
        """
        Get VM state by name.

        Args:
            vm_name: VM name

        Returns:
            VMState object

        Raises:
            VMNotFoundError: If VM not found
        """
        return self.state_service.get_vm_state(vm_name)

    def get_vm_for_app(self, app_name: str) -> Tuple[str, str]:
        """
        Get VM name and IP for application.

        Args:
            app_name: Application name

        Returns:
            Tuple of (vm_name, vm_ip)

        Raises:
            AppNotFoundError: If app not found in config
            VMNotFoundError: If VM for app not found in state
        """
        # Get VM role from config
        try:
            vm_role = self.config_service.get_app_vm_role(self.project_name, app_name)
        except KeyError:
            available_apps = self.config_service.list_apps(self.project_name)
            raise AppNotFoundError(app_name, self.project_name, available_apps)

        # Get VM IP directly from database (most reliable source)
        vm_name, vm_ip = self._get_vm_from_db(vm_role)
        return vm_name, vm_ip

    def _get_vm_from_db(self, vm_role: str) -> Tuple[str, str]:
        """
        Get VM name and IP from database by role.

        Args:
            vm_role: VM role (e.g., "app", "core")

        Returns:
            Tuple of (vm_name, vm_ip)

        Raises:
            VMNotFoundError: If VM not found
        """
        from cli.database import get_db_session, VM, Project

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                raise VMNotFoundError(vm_role, [])

            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.role == vm_role)
                .first()
            )

            if not vm or not vm.external_ip:
                # Get available VMs for error message
                all_vms = db.query(VM).filter(VM.project_id == project.id).all()
                available = [v.role for v in all_vms]
                raise VMNotFoundError(vm_role, available)

            return vm.name, vm.external_ip
        finally:
            db.close()

    def _resolve_vm_name(self, vm_role: str) -> str:
        """
        Resolve VM name from role (handles both "core" and "core-0" formats).

        Args:
            vm_role: VM role name

        Returns:
            Resolved VM name

        Raises:
            VMNotFoundError: If VM not found
        """
        state = self.state_service.load_state()

        # Try with -0 suffix first (Terraform naming, has IPs)
        vm_with_suffix = f"{vm_role}-0"
        if vm_with_suffix in state.vms and state.vms[vm_with_suffix].external_ip:
            return vm_with_suffix

        # Try exact role match (only if it has an IP)
        if vm_role in state.vms and state.vms[vm_role].external_ip:
            return vm_role

        # Fallback: try with -0 suffix without IP check
        if vm_with_suffix in state.vms:
            return vm_with_suffix

        # Fallback: try exact role match without IP check
        if vm_role in state.vms:
            return vm_role

        # Not found - raise with available VMs
        available_vms = list(state.vms.keys())
        raise VMNotFoundError(vm_role, available_vms)

    def resolve_vm_ip(self, vm_identifier: str, ip_type: str = "external") -> str:
        """
        Resolve VM IP from various identifier formats.

        Args:
            vm_identifier: VM name or role (e.g., "core-0", "core", "app")
            ip_type: "external" or "internal"

        Returns:
            IP address string

        Raises:
            VMNotFoundError: If VM not found
        """
        # Check if it's a full VM name (with index suffix)
        if "-" in vm_identifier and vm_identifier.split("-")[-1].isdigit():
            return self.state_service.get_vm_ip(vm_identifier, ip_type)

        # It's a role - resolve to actual VM name first
        vm_name = self._resolve_vm_name(vm_identifier)
        return self.state_service.get_vm_ip(vm_name, ip_type)

    def get_all_vms(self) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Get all VMs with their IPs and status.

        Returns:
            Dictionary of VM states
        """
        return self.state_service.get_all_vms()

    def get_all_vm_ips(self, ip_type: str = "external") -> Dict[str, str]:
        """
        Get all VM IPs of specified type.

        Args:
            ip_type: "external" or "internal"

        Returns:
            Dictionary of {vm_name: ip_address}
        """
        return self.state_service.get_all_vm_ips(ip_type)

    def get_vm_role_from_name(self, vm_name: str) -> str:
        """
        Extract role from VM name.

        Examples:
            "core-0" → "core"
            "app-0" → "app"
            "core" → "core"

        Args:
            vm_name: VM name

        Returns:
            Role name
        """
        if "-" in vm_name and vm_name.split("-")[-1].isdigit():
            return vm_name.rsplit("-", 1)[0]
        return vm_name

    def get_ssh_config(self) -> SSHConfig:
        """
        Get SSH configuration for project.

        Returns:
            SSHConfig object
        """
        ssh_config_dict = self.config_service.get_ssh_config(self.project_name)
        return SSHConfig(
            key_path=ssh_config_dict["key_path"],
            user=ssh_config_dict["user"],
            public_key_path=ssh_config_dict.get("public_key_path"),
        )

    def get_ssh_service(self) -> SSHService:
        """
        Get configured SSHService for this project.

        Returns:
            SSHService instance
        """
        ssh_config = self.get_ssh_config()
        return SSHService(ssh_config)

    def check_vm_connectivity(self, vm_name: str) -> bool:
        """
        Check if VM is reachable via SSH.

        Args:
            vm_name: VM name

        Returns:
            True if SSH connection successful
        """
        try:
            vm_ip = self.state_service.get_vm_ip(vm_name, "external")
            ssh_service = self.get_ssh_service()
            return ssh_service.test_connection(vm_ip)
        except Exception:
            return False

    def list_vm_names(self) -> list[str]:
        """
        Get list of all VM names in deployment.

        Returns:
            List of VM names
        """
        state = self.state_service.load_state()
        return list(state.vms.keys())
