"""
State Manager - DB-based wrapper (replaces file-based state.yml)

This is a compatibility layer. All state is now stored in database (projects.actual_state JSON column).
This class provides backward-compatible interface while using database underneath.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class StateManager:
    """State Manager - Now uses database instead of state.yml"""

    def __init__(self, project_root: Path, project_name: str):
        """Initialize state manager with database backend"""
        self.project_root = project_root
        self.project_name = project_name

    def load_state(self) -> Dict[str, Any]:
        """Load state from database"""
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )

            if db_project and db_project.actual_state:
                return db_project.actual_state
            return {}
        finally:
            db.close()

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state to database"""
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )

            if db_project:
                db_project.actual_state = state
                db_project.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def is_deployed(self) -> bool:
        """Check if project is deployed"""
        state = self.load_state()
        return state.get("deployed", False)

    def get_ip(self, role: str = "app") -> Optional[str]:
        """Get IP for a VM role"""
        state = self.load_state()
        vms = state.get("vms", {})

        # Try to get IP from VMs
        for vm_name, vm_data in vms.items():
            if vm_data.get("role") == role:
                return vm_data.get("external_ip")

        # Fallback: try to get first VM IP
        if vms:
            first_vm = next(iter(vms.values()))
            return first_vm.get("external_ip")

        return None

    def _calculate_config_hash(self) -> str:
        """Calculate config hash for change detection"""
        import hashlib
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )

            if db_project:
                # Create a string from all config fields
                config_str = f"{db_project.gcp_project}{db_project.gcp_region}{db_project.gcp_zone}"
                return hashlib.sha256(config_str.encode()).hexdigest()
            return ""
        finally:
            db.close()

    def detect_changes(self, project_config):
        """
        Detect changes between current config and deployed state.

        Args:
            project_config: ProjectConfig object with current configuration

        Returns:
            Tuple of (changes dict, state dict)
        """
        state = self.load_state()
        config = project_config.raw_config

        changes = {
            "has_changes": False,
            "total_changes": 0,
            "vms": {"added": [], "removed": [], "modified": []},
            "addons": {"added": [], "removed": [], "modified": []},
            "apps": {"added": [], "removed": [], "modified": []},
            "needs_terraform": False,
            "needs_ansible": False,
            "needs_generate": False,
            "needs_sync": False,
        }

        # Check VMs
        config_vms = set(config.get("vms", {}).keys())
        state_vms = set(state.get("vms", {}).keys())

        changes["vms"]["added"] = list(config_vms - state_vms)
        changes["vms"]["removed"] = list(state_vms - config_vms)

        # Check for modified VMs
        for vm_name in config_vms & state_vms:
            config_vm = config["vms"][vm_name]
            state_vm = state["vms"][vm_name]

            if self._vm_changed(config_vm, state_vm):
                changes["vms"]["modified"].append(
                    {
                        "name": vm_name,
                        "old": state_vm,
                        "new": config_vm,
                    }
                )

        # Check Addons
        config_addons = self._get_enabled_addons(config)
        state_addons = set(state.get("addons", {}).keys())

        changes["addons"]["added"] = list(config_addons - state_addons)
        changes["addons"]["removed"] = list(state_addons - config_addons)

        # Check Apps
        config_apps = set(config.get("apps", {}).keys())
        state_apps = set(state.get("apps", {}).keys())

        changes["apps"]["added"] = list(config_apps - state_apps)
        changes["apps"]["removed"] = list(state_apps - config_apps)

        # Check for modified apps
        for app_name in config_apps & state_apps:
            config_app = config["apps"][app_name]
            state_app = state["apps"][app_name]

            if self._app_changed(config_app, state_app):
                changes["apps"]["modified"].append(
                    {
                        "name": app_name,
                        "old": state_app,
                        "new": config_app,
                    }
                )

        # Determine what actions are needed
        if (
            changes["vms"]["added"]
            or changes["vms"]["removed"]
            or changes["vms"]["modified"]
        ):
            changes["needs_terraform"] = True
            changes["has_changes"] = True
            changes["total_changes"] += (
                len(changes["vms"]["added"])
                + len(changes["vms"]["removed"])
                + len(changes["vms"]["modified"])
            )

        if (
            changes["addons"]["added"]
            or changes["addons"]["removed"]
            or changes["addons"]["modified"]
        ):
            changes["needs_ansible"] = True
            changes["has_changes"] = True
            changes["total_changes"] += (
                len(changes["addons"]["added"])
                + len(changes["addons"]["removed"])
                + len(changes["addons"]["modified"])
            )

        if (
            changes["apps"]["added"]
            or changes["apps"]["removed"]
            or changes["apps"]["modified"]
        ):
            changes["needs_generate"] = True
            changes["needs_ansible"] = True
            changes["has_changes"] = True
            changes["total_changes"] += (
                len(changes["apps"]["added"])
                + len(changes["apps"]["removed"])
                + len(changes["apps"]["modified"])
            )

        return changes, state

    def _vm_changed(self, config_vm: dict, state_vm: dict) -> bool:
        """Check if VM configuration changed."""
        keys_to_compare = ["machine_type", "disk_size"]
        for key in keys_to_compare:
            if config_vm.get(key) != state_vm.get(key):
                return True
        return False

    def _app_changed(self, config_app: dict, state_app: dict) -> bool:
        """Check if app configuration changed."""
        keys_to_compare = ["path", "vm", "port"]
        for key in keys_to_compare:
            if config_app.get(key) != state_app.get(key):
                return True
        return False

    def _get_enabled_addons(self, config: dict) -> set:
        """Get list of enabled addons from config."""
        enabled = set()
        addons_config = config.get("addons", {})

        for category, category_addons in addons_config.items():
            if isinstance(category_addons, dict):
                for addon_name, addon_conf in category_addons.items():
                    if addon_conf and addon_conf.get("enabled", True):
                        enabled.add(f"{category}.{addon_name}")

        return enabled

    def mark_vms_provisioned(
        self, vms_config: dict, vm_ips: Optional[dict] = None
    ) -> None:
        """
        Mark VMs as provisioned in state.

        Args:
            vms_config: VM configuration from config.yml
            vm_ips: Optional dict with 'external' and 'internal' IP mappings
        """
        state = self.load_state()

        # Initialize VMs in state
        if "vms" not in state:
            state["vms"] = {}

        for vm_name, vm_config in vms_config.items():
            state["vms"][vm_name] = {
                "role": vm_config.get("role"),
                "machine_type": vm_config.get("machine_type"),
                "disk_size": vm_config.get("disk_size"),
                "status": "provisioned",  # VMs are provisioned but not configured yet
            }

            # Add IPs if provided
            if vm_ips:
                external_ips = vm_ips.get("external", {})
                internal_ips = vm_ips.get("internal", {})

                if vm_name in external_ips:
                    state["vms"][vm_name]["external_ip"] = external_ips[vm_name]
                if vm_name in internal_ips:
                    state["vms"][vm_name]["internal_ip"] = internal_ips[vm_name]

        state["deployed"] = True
        state["last_updated"] = datetime.utcnow().isoformat()

        self.save_state(state)

    def mark_vms_configured(self, vm_names: list) -> None:
        """
        Mark VMs as configured (Ansible completed).

        Args:
            vm_names: List of VM names that were configured
        """
        state = self.load_state()

        if "vms" not in state:
            state["vms"] = {}

        for vm_name in vm_names:
            if vm_name in state["vms"]:
                state["vms"][vm_name]["status"] = "configured"

        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)

    def mark_foundation_complete(self) -> None:
        """Mark foundation setup as complete (base system + Docker installed)."""
        state = self.load_state()
        state["foundation_complete"] = True
        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)

    def mark_deployment_complete(self) -> None:
        """Mark entire deployment as complete."""
        state = self.load_state()
        state["deployed"] = True
        state["deployment_complete"] = True
        state["deployed_at"] = datetime.utcnow().isoformat()
        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)

    def update_from_config(self, project_config) -> None:
        """
        Update state from project configuration after successful deployment.

        Args:
            project_config: ProjectConfig object with current configuration
        """
        state = self.load_state()
        config = project_config.raw_config

        # Update VMs from config
        if "vms" not in state:
            state["vms"] = {}

        for vm_name, vm_config in config.get("vms", {}).items():
            if vm_name not in state["vms"]:
                state["vms"][vm_name] = {}
            # Update config info but preserve runtime info (IPs, status)
            state["vms"][vm_name].update(
                {
                    "role": vm_config.get("role", vm_name),
                    "machine_type": vm_config.get("machine_type"),
                    "disk_size": vm_config.get("disk_size"),
                }
            )

        # Update apps from config
        state["apps"] = config.get("apps", {})

        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)

    def mark_addon_deployed(self, addon_name: str, status: str = "deployed") -> None:
        """
        Mark a single addon as deployed.

        Args:
            addon_name: Name of the addon that was deployed
            status: Status to set (default: "deployed")
        """
        state = self.load_state()

        if "addons" not in state:
            state["addons"] = {}

        state["addons"][addon_name] = {
            "status": status,
            "deployed_at": datetime.utcnow().isoformat(),
        }

        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)

    def mark_addons_deployed(self, addon_names: list) -> None:
        """
        Mark addons as deployed.

        Args:
            addon_names: List of addon names that were deployed
        """
        state = self.load_state()

        if "addons" not in state:
            state["addons"] = {}

        for addon_name in addon_names:
            state["addons"][addon_name] = {
                "status": "deployed",
                "deployed_at": datetime.utcnow().isoformat(),
            }

        state["last_updated"] = datetime.utcnow().isoformat()
        self.save_state(state)
