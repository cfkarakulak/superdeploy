"""
State Management Service

Centralized state loading, VM IP resolution, and state updates.
Used by 20+ commands that need deployment state access.
"""

from pathlib import Path
from typing import Dict, Optional, Any
from cli.state_manager import StateManager


class StateService:
    """
    Centralized state management service.

    Responsibilities:
    - Load and cache project state
    - VM IP resolution
    - State updates
    - Common error handling for missing state
    """

    def __init__(self, project_root: Path, project_name: str):
        self.project_root = project_root
        self.project_name = project_name
        self.state_manager = StateManager(project_root, project_name)
        self._state_cache: Optional[Dict[str, Any]] = None

    def load_state(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load project state with caching.

        Args:
            force_reload: Force reload from disk, ignore cache

        Returns:
            State dictionary

        Raises:
            RuntimeError: If state not found or invalid
        """
        if self._state_cache is None or force_reload:
            self._state_cache = self.state_manager.load_state()

            if not self._state_cache:
                raise RuntimeError(
                    f"No deployment state found for project '{self.project_name}'\n"
                    f"Run: superdeploy {self.project_name}:up"
                )

            if "vms" not in self._state_cache:
                raise RuntimeError(
                    f"Invalid state: no VMs found for project '{self.project_name}'"
                )

        return self._state_cache

    def get_vm_ip(self, vm_name: str, ip_type: str = "external") -> str:
        """
        Get VM IP address by name.

        Args:
            vm_name: VM name (e.g., "core-0", "app-0")
            ip_type: "external" or "internal"

        Returns:
            IP address string

        Raises:
            RuntimeError: If VM or IP not found
        """
        state = self.load_state()
        vms = state.get("vms", {})

        if vm_name not in vms:
            raise RuntimeError(
                f"VM '{vm_name}' not found in state\n"
                f"Available VMs: {', '.join(vms.keys())}"
            )

        ip_key = f"{ip_type}_ip"
        if ip_key not in vms[vm_name]:
            raise RuntimeError(
                f"No {ip_type} IP found for VM '{vm_name}'\n"
                f"Run: superdeploy {self.project_name}:up"
            )

        return vms[vm_name][ip_key]

    def get_vm_ip_by_role(
        self, vm_role: str, ip_type: str = "external", index: int = 0
    ) -> str:
        """
        Get VM IP by role and index.

        Args:
            vm_role: VM role (e.g., "core", "app")
            ip_type: "external" or "internal"
            index: VM index (default: 0)

        Returns:
            IP address string
        """
        vm_name = f"{vm_role}-{index}"
        return self.get_vm_ip(vm_name, ip_type)

    def get_all_vm_ips(self, ip_type: str = "external") -> Dict[str, str]:
        """
        Get all VM IPs as dictionary.

        Args:
            ip_type: "external" or "internal"

        Returns:
            Dictionary of {vm_name: ip_address}
        """
        state = self.load_state()
        vms = state.get("vms", {})

        result = {}
        ip_key = f"{ip_type}_ip"

        for vm_name, vm_data in vms.items():
            if ip_key in vm_data:
                result[vm_name] = vm_data[ip_key]

        return result

    def get_env_dict(self) -> Dict[str, str]:
        """
        Get environment dictionary compatible with old load_env() format.

        Returns:
            Dictionary with VM_NAME_EXTERNAL_IP style keys
        """
        env = {}
        state = self.load_state()
        vms = state.get("vms", {})

        for vm_name, vm_data in vms.items():
            if "external_ip" in vm_data:
                env_key = vm_name.upper().replace("-", "_")
                env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

            if "internal_ip" in vm_data:
                env_key = vm_name.upper().replace("-", "_")
                env[f"{env_key}_INTERNAL_IP"] = vm_data["internal_ip"]

        return env

    def has_state(self) -> bool:
        """
        Check if state exists without raising error.

        Returns:
            True if state exists and valid
        """
        try:
            self.load_state()
            return True
        except RuntimeError:
            return False

    def save_state(self, config: Dict[str, Any], state_data: Dict[str, Any]) -> None:
        """
        Save state to disk.

        Args:
            config: Project config
            state_data: State data (vms, addons, apps)
        """
        self.state_manager.save_state(config, state_data)
        self._state_cache = None  # Invalidate cache

    def mark_destroyed(self) -> None:
        """Mark project as destroyed in state."""
        self.state_manager.mark_destroyed()
        self._state_cache = None

    def update_vm_ips(
        self,
        vm_name: str,
        external_ip: Optional[str] = None,
        internal_ip: Optional[str] = None,
    ) -> None:
        """
        Update VM IPs in state.

        Args:
            vm_name: VM name
            external_ip: External IP (optional)
            internal_ip: Internal IP (optional)
        """
        state = self.load_state()

        if "vms" not in state:
            state["vms"] = {}

        if vm_name not in state["vms"]:
            state["vms"][vm_name] = {}

        if external_ip:
            state["vms"][vm_name]["external_ip"] = external_ip

        if internal_ip:
            state["vms"][vm_name]["internal_ip"] = internal_ip

        # Save with existing config
        config = state.get("config", {})
        state_data = {
            "vms": state["vms"],
            "addons": state.get("addons", {}),
            "apps": state.get("apps", {}),
        }

        self.save_state(config, state_data)

    def clear_cache(self) -> None:
        """Clear cached state, force reload on next access."""
        self._state_cache = None
