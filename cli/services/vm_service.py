"""
VM Management Service

Centralized VM queries, IP resolution, and status checks.
Combines StateService and ConfigService for VM operations.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
from .state_service import StateService
from .config_service import ConfigService
from .ssh_service import SSHService


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
        self.project_root = project_root
        self.project_name = project_name
        self.state_service = StateService(project_root, project_name)
        self.config_service = ConfigService(project_root)

    def get_vm_for_app(self, app_name: str) -> Tuple[str, str]:
        """
        Get VM name and IP for app.

        Args:
            app_name: App name

        Returns:
            Tuple of (vm_name, vm_ip)
        """
        # Get VM role from config
        vm_role = self.config_service.get_app_vm_role(self.project_name, app_name)

        # Default to first VM of that role
        vm_name = f"{vm_role}-0"

        # Get IP from state
        vm_ip = self.state_service.get_vm_ip(vm_name)

        return vm_name, vm_ip

    def resolve_vm_ip(self, vm_identifier: str, ip_type: str = "external") -> str:
        """
        Resolve VM IP from various identifier formats.

        Args:
            vm_identifier: VM name or role (e.g., "core-0", "core", "app")
            ip_type: "external" or "internal"

        Returns:
            IP address
        """
        # Check if it's a full VM name (with index)
        if "-" in vm_identifier and vm_identifier.split("-")[-1].isdigit():
            return self.state_service.get_vm_ip(vm_identifier, ip_type)

        # It's a role, default to index 0
        return self.state_service.get_vm_ip_by_role(vm_identifier, ip_type, index=0)

    def get_all_vms(self) -> Dict[str, Dict[str, str]]:
        """
        Get all VMs with their IPs.

        Returns:
            Dictionary of {vm_name: {"external_ip": "...", "internal_ip": "..."}}
        """
        external_ips = self.state_service.get_all_vm_ips("external")
        internal_ips = self.state_service.get_all_vm_ips("internal")

        result = {}
        for vm_name in external_ips:
            result[vm_name] = {
                "external_ip": external_ips[vm_name],
                "internal_ip": internal_ips.get(vm_name, ""),
            }

        return result

    def check_vm_health(
        self, vm_name: str, ssh_service: Optional[SSHService] = None
    ) -> bool:
        """
        Check if VM is healthy (SSH accessible).

        Args:
            vm_name: VM name
            ssh_service: Optional SSHService instance (creates new if None)

        Returns:
            True if healthy
        """
        try:
            vm_ip = self.state_service.get_vm_ip(vm_name)

            if ssh_service is None:
                ssh_config = self.config_service.get_ssh_config(self.project_name)
                ssh_service = SSHService(
                    ssh_key_path=ssh_config["key_path"], ssh_user=ssh_config["user"]
                )

            return ssh_service.test_connection(vm_ip)
        except Exception:
            return False

    def get_vm_role_from_name(self, vm_name: str) -> str:
        """
        Extract role from VM name.

        Args:
            vm_name: VM name (e.g., "core-0")

        Returns:
            Role name (e.g., "core")
        """
        if "-" in vm_name:
            return vm_name.rsplit("-", 1)[0]
        return vm_name

    def get_vm_index_from_name(self, vm_name: str) -> int:
        """
        Extract index from VM name.

        Args:
            vm_name: VM name (e.g., "core-0")

        Returns:
            Index (e.g., 0)
        """
        if "-" in vm_name:
            index_str = vm_name.rsplit("-", 1)[1]
            if index_str.isdigit():
                return int(index_str)
        return 0

    def list_vms_by_role(self, role: str) -> list[str]:
        """
        List all VMs for a specific role.

        Args:
            role: VM role

        Returns:
            List of VM names
        """
        all_vms = self.state_service.load_state().get("vms", {})
        return [
            vm_name
            for vm_name in all_vms.keys()
            if self.get_vm_role_from_name(vm_name) == role
        ]

    def get_primary_vm_ip(self, ip_type: str = "external") -> str:
        """
        Get primary (core-0) VM IP.

        Args:
            ip_type: "external" or "internal"

        Returns:
            IP address
        """
        return self.resolve_vm_ip("core-0", ip_type)

    def has_deployed_vms(self) -> bool:
        """
        Check if project has any deployed VMs.

        Returns:
            True if VMs exist in state
        """
        return self.state_service.has_state()

    def get_ssh_service(self) -> SSHService:
        """
        Get configured SSHService for this project.

        Returns:
            SSHService instance
        """
        ssh_config = self.config_service.get_ssh_config(self.project_name)
        return SSHService(
            ssh_key_path=ssh_config["key_path"], ssh_user=ssh_config["user"]
        )

