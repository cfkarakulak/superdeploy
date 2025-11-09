"""
VM Management Service

Centralized VM queries, IP resolution, and status checks.
Combines StateService and ConfigService for VM operations.
"""

from pathlib import Path
from typing import Dict, Tuple
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

        # Try to find VM in state (with or without suffix)
        state = self.state_service.load_state()
        vms = state.get("vms", {})
        
        # First try exact role match
        if vm_role in vms:
            vm_name = vm_role
        # Then try with -0 suffix
        elif f"{vm_role}-0" in vms:
            vm_name = f"{vm_role}-0"
        else:
            # List available VMs for better error message
            available = ", ".join(vms.keys())
            raise RuntimeError(
                f"VM '{vm_role}' or '{vm_role}-0' not found in state\n"
                f"Available VMs: {available}"
            )

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
