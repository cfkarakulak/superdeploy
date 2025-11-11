"""
State Management

Modern state manager using domain models for type-safe state handling.
"""

import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from cli.models.deployment import (
    DeploymentState,
    VMState,
    VMStatus,
    AddonState,
    AddonStatus,
    AppState,
)
from cli.exceptions import StateError


class StateFormatter:
    """Formats deployment state for human-readable YAML output."""

    @staticmethod
    def format(state: DeploymentState) -> str:
        """
        Format deployment state as human-readable YAML.

        Args:
            state: Deployment state to format

        Returns:
            Formatted YAML string
        """
        lines = []

        # Header
        lines.append("# " + "=" * 77)
        lines.append(f"# {state.project_name.upper()} - Deployment State")
        lines.append("# " + "=" * 77)
        lines.append("# This file tracks the current state of deployed infrastructure")
        lines.append("# WARNING: Do not manually edit this file")
        lines.append("# " + "=" * 77)
        lines.append("")

        # VMs section
        if state.vms:
            lines.append("# " + "=" * 77)
            lines.append("# Virtual Machines")
            lines.append("# " + "=" * 77)
            lines.append("vms:")

            for vm_name, vm_state in state.vms.items():
                lines.append("")
                lines.append(f"  {vm_name}:")
                vm_dict = vm_state.to_dict()
                for key, value in vm_dict.items():
                    if isinstance(value, list):
                        if value:
                            lines.append(f"    {key}:")
                            for item in value:
                                lines.append(f"      - {item}")
                        else:
                            lines.append(f"    {key}: []")
                    elif value is not None:
                        lines.append(f"    {key}: {value}")

        # Addons section
        if state.addons:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Installed Addons")
            lines.append("# " + "=" * 77)
            lines.append("addons:")

            for addon_name, addon_state in state.addons.items():
                lines.append("")
                lines.append(f"  {addon_name}:")
                addon_dict = addon_state.to_dict()
                for key, value in addon_dict.items():
                    if value is not None:
                        lines.append(f"    {key}: {value}")

        # Apps section
        if state.apps:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Deployed Applications")
            lines.append("# " + "=" * 77)
            lines.append("apps:")

            for app_name, app_state in state.apps.items():
                lines.append("")
                lines.append(f"  {app_name}:")
                app_dict = app_state.to_dict()
                for key, value in app_dict.items():
                    if value is not None:
                        if isinstance(value, bool):
                            lines.append(f"    {key}: {str(value).lower()}")
                        else:
                            lines.append(f"    {key}: {value}")

        # Deployment section
        if state.foundation_complete or state.deployment_complete:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Deployment Status")
            lines.append("# " + "=" * 77)
            lines.append("deployment:")
            lines.append(
                f"  foundation_complete: {str(state.foundation_complete).lower()}"
            )
            lines.append(f"  complete: {str(state.deployment_complete).lower()}")

        # Last applied section
        if state.last_applied or state.config_hash:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Last Deployment Metadata")
            lines.append("# " + "=" * 77)
            lines.append("last_applied:")
            if state.last_applied:
                lines.append(f"  timestamp: {state.last_applied}")
            if state.config_hash:
                lines.append(f"  config_hash: {state.config_hash}")

        # Secrets sync status
        if state.secrets_hash or state.secrets_last_sync:
            lines.append("")
            lines.append("# " + "=" * 77)
            lines.append("# Secrets Synchronization Status")
            lines.append("# " + "=" * 77)
            lines.append("secrets:")
            if state.secrets_hash:
                lines.append(f"  hash: {state.secrets_hash}")
            if state.secrets_last_sync:
                lines.append(f"  last_sync: {state.secrets_last_sync}")

        lines.append("")
        return "\n".join(lines)


class StateManager:
    """
    Manages project deployment state using type-safe domain models.

    Responsibilities:
    - Load/save deployment state
    - Track VM, addon, and app states
    - Detect configuration changes
    - Maintain deployment history
    """

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize state manager.

        Args:
            project_root: Path to superdeploy root directory
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.state_file = project_root / "projects" / project_name / "state.yml"
        self.formatter = StateFormatter()

    def load_state(self) -> DeploymentState:
        """
        Load deployment state from file.

        Returns:
            DeploymentState object (empty if file doesn't exist)
        """
        if not self.state_file.exists():
            return DeploymentState(project_name=self.project_name)

        try:
            with open(self.state_file, "r") as f:
                data = yaml.safe_load(f) or {}
            return DeploymentState.from_dict(self.project_name, data)
        except Exception as e:
            raise StateError(
                "Failed to load state file",
                context=f"File: {self.state_file}, Error: {str(e)}",
            )

    def save_state(self, state: DeploymentState) -> None:
        """
        Save deployment state to file.

        Args:
            state: Deployment state to save
        """
        # Update metadata
        state.last_applied = datetime.now().isoformat()
        state.config_hash = self._calculate_config_hash()

        # Format and write
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        formatted_content = self.formatter.format(state)

        try:
            with open(self.state_file, "w") as f:
                f.write(formatted_content)
        except Exception as e:
            raise StateError(
                "Failed to save state file",
                context=f"File: {self.state_file}, Error: {str(e)}",
            )

    def has_state(self) -> bool:
        """
        Check if state file exists.

        Returns:
            True if state file exists
        """
        return self.state_file.exists()

    def _calculate_config_hash(self) -> str:
        """Calculate SHA256 hash of config.yml for change detection."""
        config_file = self.project_root / "projects" / self.project_name / "config.yml"

        if not config_file.exists():
            return ""

        with open(config_file, "rb") as f:
            content = f.read()
            return hashlib.sha256(content).hexdigest()[:12]

    def _calculate_secrets_hash(self) -> str:
        """Calculate SHA256 hash of secrets.yml."""
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

    def detect_changes(
        self, project_config: Any
    ) -> Tuple[Dict[str, Any], DeploymentState]:
        """
        Detect changes between current config and deployed state.

        Args:
            project_config: Project configuration object

        Returns:
            Tuple of (changes_dict, deployment_state)
        """
        state = self.load_state()
        config = project_config.raw_config

        changes: Dict[str, Any] = {
            "has_changes": False,
            "vms": {"added": [], "removed": [], "modified": []},
            "addons": {"added": [], "removed": [], "modified": []},
            "apps": {"added": [], "removed": [], "modified": []},
            "needs_generate": False,
            "needs_terraform": False,
            "needs_ansible": False,
            "needs_sync": False,
            "needs_foundation": True,
        }

        # First deployment - no state
        if not state.has_vms:
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

        # Check foundation status
        if state.foundation_complete:
            changes["needs_foundation"] = False
        else:
            changes["needs_ansible"] = True

        # Check for provisioned but not configured VMs
        for vm_state in state.vms.values():
            if vm_state.status == VMStatus.PROVISIONED:
                changes["needs_ansible"] = True
                changes["has_changes"] = True
                break

        # Detect VM changes
        config_vms = config.get("vms", {})
        for vm_name, vm_config in config_vms.items():
            if vm_name not in state.vms:
                changes["vms"]["added"].append(vm_name)
                changes["needs_terraform"] = True
                changes["needs_ansible"] = True
            else:
                vm_state = state.vms[vm_name]
                if self._vm_config_changed(vm_config, vm_state):
                    changes["vms"]["modified"].append(
                        {
                            "name": vm_name,
                            "old": vm_state.to_dict(),
                            "new": vm_config,
                        }
                    )
                    changes["needs_terraform"] = True
                    changes["needs_ansible"] = True

        for vm_name in state.vms:
            if vm_name not in config_vms:
                changes["vms"]["removed"].append(vm_name)
                changes["needs_terraform"] = True

        # Detect addon changes
        config_addons = config.get("addons", {})
        for addon_name in config_addons:
            if addon_name not in state.addons:
                changes["addons"]["added"].append(addon_name)
                changes["needs_ansible"] = True
                changes["needs_sync"] = True

        for addon_name in state.addons:
            if addon_name not in config_addons:
                changes["addons"]["removed"].append(addon_name)
                changes["needs_ansible"] = True

        # Detect app changes
        config_apps = config.get("apps", {})
        for app_name, app_config in config_apps.items():
            if app_name not in state.apps:
                changes["apps"]["added"].append(app_name)
                changes["needs_generate"] = True
                changes["needs_sync"] = True
            else:
                app_state = state.apps[app_name]
                if self._app_config_changed(app_config, app_state):
                    changes["apps"]["modified"].append(
                        {
                            "name": app_name,
                            "old": app_state.to_dict(),
                            "new": app_config,
                        }
                    )
                    changes["needs_generate"] = True

        for app_name in state.apps:
            if app_name not in config_apps:
                changes["apps"]["removed"].append(app_name)

        # Check secrets changes
        if self._secrets_changed(state):
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
                changes["needs_sync"],
            ]
        ):
            changes["has_changes"] = True

        return changes, state

    def _vm_config_changed(self, config: Dict[str, Any], state: VMState) -> bool:
        """Check if VM configuration has changed."""
        return (
            config.get("machine_type") != state.machine_type
            or config.get("disk_size") != state.disk_size
            or set(config.get("services", [])) != set(state.services)
        )

    def _app_config_changed(self, config: Dict[str, Any], state: AppState) -> bool:
        """Check if app configuration has changed."""
        return config.get("path") != state.path or config.get("vm") != state.vm

    def _secrets_changed(self, state: DeploymentState) -> bool:
        """Check if secrets have changed since last deployment."""
        current_hash = self._calculate_secrets_hash()
        if not current_hash:
            return False

        stored_hash = state.secrets_hash
        if not stored_hash:
            return True

        return current_hash != stored_hash

    def update_from_config(self, project_config: Any) -> None:
        """
        Update state from successful deployment.

        Args:
            project_config: Project configuration object
        """
        state = self.load_state()
        config = project_config.raw_config

        # Update VMs (preserve IPs if they exist)
        for vm_name, vm_config in config.get("vms", {}).items():
            existing_vm = state.vms.get(vm_name)

            state.vms[vm_name] = VMState(
                name=vm_name,
                machine_type=vm_config.get("machine_type", ""),
                disk_size=vm_config.get("disk_size", 20),
                services=vm_config.get("services", []),
                status=VMStatus.RUNNING if existing_vm else VMStatus.PENDING,
                external_ip=existing_vm.external_ip if existing_vm else None,
                internal_ip=existing_vm.internal_ip if existing_vm else None,
            )

        # Update addons
        for addon_name in config.get("addons", {}):
            state.addons[addon_name] = AddonState(
                name=addon_name,
                status=AddonStatus.INSTALLED,
            )

        # Update apps
        for app_name, app_config in config.get("apps", {}).items():
            state.apps[app_name] = AppState(
                name=app_name,
                path=app_config.get("path", ""),
                vm=app_config.get("vm", ""),
                workflows_generated=True,
            )

        self.save_state(state)

    def mark_vms_provisioned(
        self,
        vm_configs: Dict[str, Any],
        vm_ips: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """
        Mark VMs as provisioned after Terraform success.

        Args:
            vm_configs: VM configuration from config.yml
            vm_ips: Optional dict with 'external' and 'internal' IP mappings
        """
        state = self.load_state()

        for vm_name, vm_config in vm_configs.items():
            vm_state = VMState(
                name=vm_name,
                machine_type=vm_config.get("machine_type", ""),
                disk_size=vm_config.get("disk_size", 20),
                services=vm_config.get("services", []),
                status=VMStatus.PROVISIONED,
                provisioned_at=datetime.now().isoformat(),
            )

            # Add IPs if provided
            if vm_ips:
                external_ips = vm_ips.get("external", {})
                internal_ips = vm_ips.get("internal", {})

                # Find matching IPs by prefix (e.g., "core" matches "core-0")
                for vm_key, external_ip in external_ips.items():
                    if vm_key.startswith(vm_name + "-"):
                        vm_state.external_ip = external_ip
                        break

                for vm_key, internal_ip in internal_ips.items():
                    if vm_key.startswith(vm_name + "-"):
                        vm_state.internal_ip = internal_ip
                        break

            state.vms[vm_name] = vm_state

        self.save_state(state)

    def mark_foundation_complete(self) -> None:
        """Mark foundation (base system + docker) as complete."""
        state = self.load_state()
        state.foundation_complete = True
        self.save_state(state)

    def mark_deployment_complete(self) -> None:
        """Mark full deployment as complete (after Ansible succeeds)."""
        state = self.load_state()

        # Update all VMs to running status
        for vm_state in state.vms.values():
            vm_state.status = VMStatus.RUNNING
            vm_state.configured_at = datetime.now().isoformat()

        state.deployment_complete = True
        self.save_state(state)

    def mark_addon_deployed(self, addon_name: str) -> None:
        """
        Mark specific addon as deployed.

        Args:
            addon_name: Name of the addon
        """
        state = self.load_state()

        state.addons[addon_name] = AddonState(
            name=addon_name,
            status=AddonStatus.DEPLOYED,
            deployed_at=datetime.now().isoformat(),
        )

        self.save_state(state)

    def mark_synced(self) -> None:
        """Mark secrets as synced and update secrets hash."""
        state = self.load_state()
        state.secrets_last_sync = datetime.now().isoformat()
        state.secrets_hash = self._calculate_secrets_hash()
        self.save_state(state)

    def mark_destroyed(self) -> None:
        """Mark project as destroyed and clear all state."""
        if self.state_file.exists():
            self.state_file.unlink()
