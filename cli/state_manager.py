"""State management for SuperDeploy projects"""

import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class StateManager:
    """Manages project state for change detection and idempotency"""

    def __init__(self, project_root: Path, project_name: str):
        self.project_root = project_root
        self.project_name = project_name
        self.state_file = project_root / "projects" / project_name / "state.yml"

    def load_state(self) -> Dict[str, Any]:
        """Load existing state, return empty dict if not exists"""
        if not self.state_file.exists():
            return {}

        with open(self.state_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_state(self, state: Dict[str, Any]):
        """Save state to file"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp
        state["last_applied"] = {
            "timestamp": datetime.now().isoformat(),
            "config_hash": self._calculate_config_hash(),
        }

        with open(self.state_file, "w") as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)

    def _calculate_config_hash(self) -> str:
        """Calculate hash of project.yml for change detection"""
        project_yml = self.project_root / "projects" / self.project_name / "project.yml"

        if not project_yml.exists():
            return ""

        with open(project_yml, "rb") as f:
            content = f.read()
            return hashlib.sha256(content).hexdigest()[:12]

    def detect_changes(
        self, project_config: Any
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Detect changes between current config and last applied state

        Returns:
            (changes_dict, state_dict)

        changes_dict structure:
            {
                'has_changes': bool,
                'vms': {'added': [], 'removed': [], 'modified': []},
                'addons': {'added': [], 'removed': [], 'modified': []},
                'apps': {'added': [], 'removed': [], 'modified': []},
                'needs_generate': bool,
                'needs_terraform': bool,
                'needs_ansible': bool,
                'needs_sync': bool
            }
        """
        state = self.load_state()
        config = project_config.raw_config

        changes = {
            "has_changes": False,
            "vms": {"added": [], "removed": [], "modified": []},
            "addons": {"added": [], "removed": [], "modified": []},
            "apps": {"added": [], "removed": [], "modified": []},
            "needs_generate": False,
            "needs_terraform": False,
            "needs_ansible": False,
            "needs_sync": False,
            "needs_foundation": True,  # Assume foundation needed unless proven otherwise
        }

        # First deployment (no state)
        if not state:
            # Everything is new
            config_vms = config.get("vms", {})
            config_addons = config.get("addons", {})
            config_apps = config.get("apps", {})

            changes["has_changes"] = True
            changes["vms"]["added"] = list(config_vms.keys())
            changes["addons"]["added"] = list(config_addons.keys())
            changes["apps"]["added"] = list(config_apps.keys())
            changes["needs_generate"] = bool(config_apps)
            changes["needs_terraform"] = bool(config_vms)
            changes["needs_ansible"] = bool(config_addons) or bool(config_vms)
            changes["needs_sync"] = True

            return changes, state

        # Check if foundation is already complete (for partial deployments)
        deployment_state = state.get("deployment", {})
        if deployment_state.get("foundation_complete"):
            changes["needs_foundation"] = False
        else:
            # Foundation not complete = needs Ansible for base system + docker
            changes["needs_ansible"] = True

        # Check VMs
        state_vms = state.get("vms", {})
        config_vms = config.get("vms", {})

        for vm_name, vm_config in config_vms.items():
            if vm_name not in state_vms:
                changes["vms"]["added"].append(vm_name)
                changes["needs_terraform"] = True
                changes["needs_ansible"] = True
            else:
                # Check if VM config changed (machine_type, disk_size, services)
                state_vm = state_vms[vm_name]
                if (
                    vm_config.get("machine_type") != state_vm.get("machine_type")
                    or vm_config.get("disk_size") != state_vm.get("disk_size")
                    or set(vm_config.get("services", []))
                    != set(state_vm.get("services", []))
                ):
                    changes["vms"]["modified"].append(
                        {
                            "name": vm_name,
                            "old": state_vm,
                            "new": vm_config,
                        }
                    )
                    changes["needs_terraform"] = True
                    changes["needs_ansible"] = True

        for vm_name in state_vms:
            if vm_name not in config_vms:
                changes["vms"]["removed"].append(vm_name)
                changes["needs_terraform"] = True

        # Check Addons
        state_addons = state.get("addons", {})
        config_addons = config.get("addons", {})

        for addon_name in config_addons:
            if addon_name not in state_addons:
                changes["addons"]["added"].append(addon_name)
                changes["needs_ansible"] = True
                changes["needs_sync"] = True

        for addon_name in state_addons:
            if addon_name not in config_addons:
                changes["addons"]["removed"].append(addon_name)
                changes["needs_ansible"] = True

        # Check Apps
        state_apps = state.get("apps", {})
        config_apps = config.get("apps", {})

        for app_name, app_config in config_apps.items():
            if app_name not in state_apps:
                changes["apps"]["added"].append(app_name)
                changes["needs_generate"] = True
                changes["needs_sync"] = True
            else:
                # Check if app path or vm changed
                state_app = state_apps[app_name]
                if app_config.get("path") != state_app.get("path") or app_config.get(
                    "vm"
                ) != state_app.get("vm"):
                    changes["apps"]["modified"].append(
                        {
                            "name": app_name,
                            "old": state_app,
                            "new": app_config,
                        }
                    )
                    changes["needs_generate"] = True

        for app_name in state_apps:
            if app_name not in config_apps:
                changes["apps"]["removed"].append(app_name)
                # No action needed for removed apps

        # Check secrets.yml changes
        secrets_changed = self._check_secrets_changes(state)
        if secrets_changed:
            changes["needs_sync"] = True

        # Set has_changes flag
        if any(
            [
                changes["vms"]["added"],
                changes["vms"]["removed"],
                changes["vms"]["modified"],
                changes["addons"]["added"],
                changes["addons"]["removed"],
                changes["apps"]["added"],
                changes["apps"]["modified"],
                changes["apps"]["removed"],
                secrets_changed,
            ]
        ):
            changes["has_changes"] = True

        return changes, state

    def update_from_config(self, project_config: Any):
        """Update state from successful deployment"""
        config = project_config.raw_config

        # Load existing state to preserve IPs and other runtime data
        state = self.load_state()

        if "vms" not in state:
            state["vms"] = {}
        if "addons" not in state:
            state["addons"] = {}
        if "apps" not in state:
            state["apps"] = {}

        # Update VM state (preserve existing IPs if present)
        for vm_name, vm_config in config.get("vms", {}).items():
            # Get existing VM state to preserve IPs
            existing_vm = state["vms"].get(vm_name, {})

            state["vms"][vm_name] = {
                "machine_type": vm_config.get("machine_type"),
                "disk_size": vm_config.get("disk_size"),
                "services": vm_config.get("services", []),
                "status": "applied",
                # Preserve IPs if they exist
                "external_ip": existing_vm.get("external_ip"),
                "internal_ip": existing_vm.get("internal_ip"),
            }

            # Remove None values
            state["vms"][vm_name] = {
                k: v for k, v in state["vms"][vm_name].items() if v is not None
            }

        # Store addon state
        for addon_name in config.get("addons", {}):
            state["addons"][addon_name] = {
                "status": "installed",
            }

        # Store app state
        for app_name, app_config in config.get("apps", {}).items():
            state["apps"][app_name] = {
                "path": app_config.get("path"),
                "vm": app_config.get("vm"),
                "workflows_generated": True,
            }

        self.save_state(state)

    def mark_synced(self):
        """Mark secrets as synced and update secrets hash"""
        state = self.load_state()

        if "secrets" not in state:
            state["secrets"] = {}

        state["secrets"]["last_sync"] = datetime.now().isoformat()

        # Update secrets hash
        secrets_hash = self._get_secrets_hash()
        if secrets_hash:
            state["secrets"]["hash"] = secrets_hash

        self.save_state(state)

    def mark_vms_provisioned(self, vm_configs: dict, vm_ips: dict = None):
        """
        Mark VMs as provisioned (after Terraform success)

        Args:
            vm_configs: VM configuration from project.yml
            vm_ips: Optional dict with 'external' and 'internal' IP mappings
        """
        state = self.load_state()

        if "vms" not in state:
            state["vms"] = {}

        for vm_name, vm_config in vm_configs.items():
            state["vms"][vm_name] = {
                "machine_type": vm_config.get("machine_type"),
                "disk_size": vm_config.get("disk_size"),
                "services": vm_config.get("services", []),
                "status": "provisioned",
                "provisioned_at": datetime.now().isoformat(),
            }

            # Add IPs if provided
            if vm_ips:
                external_ips = vm_ips.get("external", {})
                internal_ips = vm_ips.get("internal", {})

                # VM name format: "core" or "app" (from vms section in project.yml)
                # Terraform output format: "core-0", "app-0", "app-1", etc.
                # Find matching IPs by prefix
                for vm_key, external_ip in external_ips.items():
                    if vm_key.startswith(vm_name + "-"):
                        state["vms"][vm_name]["external_ip"] = external_ip
                        break

                for vm_key, internal_ip in internal_ips.items():
                    if vm_key.startswith(vm_name + "-"):
                        state["vms"][vm_name]["internal_ip"] = internal_ip
                        break

        self.save_state(state)

    def mark_foundation_complete(self):
        """Mark foundation (base system + docker) as complete"""
        state = self.load_state()

        if "deployment" not in state:
            state["deployment"] = {}

        state["deployment"]["foundation_complete"] = True
        state["deployment"]["foundation_completed_at"] = datetime.now().isoformat()

        self.save_state(state)

    def mark_addon_deployed(self, addon_name: str):
        """Mark specific addon as deployed"""
        state = self.load_state()

        if "addons" not in state:
            state["addons"] = {}

        state["addons"][addon_name] = {
            "status": "deployed",
            "deployed_at": datetime.now().isoformat(),
        }

        self.save_state(state)

    def mark_destroyed(self):
        """Mark project as destroyed and clear all state"""
        # Delete the entire state file
        if self.state_file.exists():
            self.state_file.unlink()

    def _get_secrets_hash(self) -> str:
        """Calculate SHA256 hash of secrets.yml file"""
        secrets_file = (
            self.project_root / "projects" / self.project_name / "secrets.yml"
        )

        if not secrets_file.exists():
            return ""

        try:
            with open(secrets_file, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def _check_secrets_changes(self, state: Dict[str, Any]) -> bool:
        """Check if secrets.yml has changed since last deployment"""
        if not state:
            # First deployment - secrets exist
            return True

        # Get current secrets hash
        current_hash = self._get_secrets_hash()
        if not current_hash:
            # No secrets file - no changes
            return False

        # Get stored hash from state
        stored_hash = state.get("secrets", {}).get("hash", "")

        # If no stored hash, consider it changed
        if not stored_hash:
            return True

        # Compare hashes
        return current_hash != stored_hash
