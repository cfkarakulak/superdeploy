"""
State Management Service

Centralized state loading, VM IP resolution, and state updates using domain models.
"""

from pathlib import Path
from typing import Dict, Optional

from cli.state_manager import StateManager
from cli.models.deployment import DeploymentState, VMState
from cli.exceptions import StateError, VMNotFoundError, ProjectNotDeployedError


class StateService:
    """
    Centralized state management service with type-safe models.

    Responsibilities:
    - Load and cache project state
    - VM IP resolution
    - State query operations
    - Deployment status checks
    """

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize state service.

        Args:
            project_root: Path to superdeploy root directory
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.state_manager = StateManager(project_root, project_name)
        self._state_cache: Optional[DeploymentState] = None

    def load_state(self, force_reload: bool = False) -> DeploymentState:
        """
        Load project deployment state with caching.

        Args:
            force_reload: Force reload from disk, ignore cache

        Returns:
            DeploymentState object

        Raises:
            ProjectNotDeployedError: If state not found or invalid
        """
        if self._state_cache is None or force_reload:
            self._state_cache = self.state_manager.load_state()

            if not self._state_cache.has_vms:
                raise ProjectNotDeployedError(self.project_name)

        return self._state_cache

    def get_vm_state(self, vm_name: str) -> VMState:
        """
        Get VM state by name.

        Args:
            vm_name: VM name (e.g., "core", "app")

        Returns:
            VMState object

        Raises:
            VMNotFoundError: If VM not found
        """
        state = self.load_state()
        vm_state = state.get_vm(vm_name)

        if vm_state is None:
            available_vms = list(state.vms.keys())
            raise VMNotFoundError(vm_name, available_vms)

        return vm_state

    def get_vm_ip(self, vm_name: str, ip_type: str = "external") -> str:
        """
        Get VM IP address by name.

        Args:
            vm_name: VM name (e.g., "core", "app")
            ip_type: "external" or "internal"

        Returns:
            IP address string

        Raises:
            VMNotFoundError: If VM not found
            StateError: If IP not available
        """
        vm_state = self.get_vm_state(vm_name)

        if ip_type == "external":
            if vm_state.external_ip is None:
                raise StateError(
                    f"No external IP found for VM '{vm_name}'",
                    context=f"Run: superdeploy {self.project_name}:up",
                )
            return vm_state.external_ip
        elif ip_type == "internal":
            if vm_state.internal_ip is None:
                raise StateError(
                    f"No internal IP found for VM '{vm_name}'",
                    context=f"Run: superdeploy {self.project_name}:up",
                )
            return vm_state.internal_ip
        else:
            raise ValueError(
                f"Invalid IP type: {ip_type}. Must be 'external' or 'internal'"
            )

    def get_vm_ip_by_role(
        self, vm_role: str, ip_type: str = "external", index: int = 0
    ) -> str:
        """
        Get VM IP by role and index (for multi-VM setups).

        Args:
            vm_role: VM role (e.g., "core", "app")
            ip_type: "external" or "internal"
            index: VM index (default: 0)

        Returns:
            IP address string

        Raises:
            VMNotFoundError: If VM not found
        """
        # For now, we use simple naming: role = name
        # In future with multi-VM: vm_name = f"{vm_role}-{index}"
        return self.get_vm_ip(vm_role, ip_type)

    def get_all_vm_ips(self, ip_type: str = "external") -> Dict[str, str]:
        """
        Get all VM IPs as dictionary.

        Args:
            ip_type: "external" or "internal"

        Returns:
            Dictionary of {vm_name: ip_address}
        """
        state = self.load_state()
        result: Dict[str, str] = {}

        for vm_name, vm_state in state.vms.items():
            if ip_type == "external" and vm_state.external_ip:
                result[vm_name] = vm_state.external_ip
            elif ip_type == "internal" and vm_state.internal_ip:
                result[vm_name] = vm_state.internal_ip

        return result

    def get_all_vms(self) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Get all VMs with their details.

        Returns:
            Dictionary of VM states as dicts
        """
        state = self.load_state()
        return {
            vm_name: {
                "external_ip": vm.external_ip,
                "internal_ip": vm.internal_ip,
                "status": vm.status.value,
                "machine_type": vm.machine_type,
            }
            for vm_name, vm in state.vms.items()
        }

    def has_state(self) -> bool:
        """
        Check if state exists without raising error.

        Returns:
            True if state exists and has VMs
        """
        try:
            state = self.load_state()
            return state.has_vms
        except Exception:
            return False

    def is_deployed(self) -> bool:
        """
        Check if project is fully deployed.

        Returns:
            True if deployment is complete
        """
        try:
            state = self.load_state()
            return state.is_deployed
        except Exception:
            return False

    def invalidate_cache(self) -> None:
        """Invalidate the state cache to force reload on next access."""
        self._state_cache = None

    def mark_destroyed(self) -> None:
        """
        Mark project as destroyed and clear state.

        This removes the state file and invalidates cache.
        """
        self.state_manager.mark_destroyed()
        self._state_cache = None
