"""
State Manager - DB-based state management

Reads state from proper database tables (vms, apps, addons) instead of JSON columns.
This provides a cleaner, normalized data structure.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class StateManager:
    """State Manager - Reads from proper database tables"""

    def __init__(self, project_root: Path, project_name: str):
        """Initialize state manager with database backend"""
        self.project_root = project_root
        self.project_name = project_name

    def load_state(self) -> Dict[str, Any]:
        """Load state from database tables (vms, apps, addons)"""
        from cli.database import get_db_session, Project, VM, App, Addon

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return {}

            state = {"vms": {}, "apps": {}, "addons": {}, "deployed": False}

            # Load VMs
            vms = db.query(VM).filter(VM.project_id == project.id).all()
            for vm in vms:
                state["vms"][vm.name] = {
                    "role": vm.role,
                    "external_ip": vm.external_ip,
                    "internal_ip": vm.internal_ip,
                    "status": vm.status or "unknown",
                    "machine_type": vm.machine_type,
                    "disk_size": vm.disk_size,
                }
                # Mark as deployed if at least one VM has an IP
                if vm.external_ip and vm.status == "running":
                    state["deployed"] = True

            # Load Apps
            apps = db.query(App).filter(App.project_id == project.id).all()
            for app in apps:
                state["apps"][app.name] = {
                    "path": app.path,
                    "vm": app.vm,
                    "port": app.port,
                    "repo": app.repo,
                }

            # Load Addons
            addons = db.query(Addon).filter(Addon.project_id == project.id).all()
            for addon in addons:
                key = f"{addon.category}.{addon.instance_name}"
                state["addons"][key] = {
                    "type": addon.type,
                    "status": "deployed",
                    "vm": addon.vm,
                }

            return state
        finally:
            db.close()

    def save_state(self, state: Dict[str, Any]) -> None:
        """
        Save state to database tables.
        This updates VMs table with the provided state.
        """
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return

            # Update VMs
            for vm_name, vm_data in state.get("vms", {}).items():
                role = vm_data.get("role")
                if not role and "-" in vm_name:
                    role = vm_name.rsplit("-", 1)[0]

                vm = (
                    db.query(VM)
                    .filter(VM.project_id == project.id, VM.role == role)
                    .first()
                )

                if vm:
                    if "external_ip" in vm_data:
                        vm.external_ip = vm_data["external_ip"]
                    if "internal_ip" in vm_data:
                        vm.internal_ip = vm_data["internal_ip"]
                    if "status" in vm_data:
                        vm.status = vm_data["status"]
                    if "machine_type" in vm_data:
                        vm.machine_type = vm_data["machine_type"]
                    if "disk_size" in vm_data:
                        vm.disk_size = vm_data["disk_size"]

            project.updated_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    def is_deployed(self) -> bool:
        """Check if project is deployed (has running VMs with IPs)"""
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return False

            # Check if any VM has an IP and is running
            vm = (
                db.query(VM)
                .filter(
                    VM.project_id == project.id,
                    VM.external_ip.isnot(None),
                    VM.status == "running",
                )
                .first()
            )

            return vm is not None
        finally:
            db.close()

    def get_ip(self, role: str = "app") -> Optional[str]:
        """Get IP for a VM role from database"""
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return None

            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.role == role)
                .first()
            )

            if vm and vm.external_ip:
                return vm.external_ip

            # Fallback: get first VM with IP
            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.external_ip.isnot(None))
                .first()
            )

            return vm.external_ip if vm else None
        finally:
            db.close()

    def mark_vms_provisioned(
        self, vms_config: dict, vm_ips: Optional[dict] = None
    ) -> None:
        """
        Mark VMs as provisioned in database.

        Args:
            vms_config: VM configuration from config.yml
            vm_ips: Optional dict with 'external' and 'internal' IP mappings
        """
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return

            external_ips = vm_ips.get("external", {}) if vm_ips else {}
            internal_ips = vm_ips.get("internal", {}) if vm_ips else {}

            for vm_name, vm_config in vms_config.items():
                role = vm_config.get("role", vm_name)

                vm = (
                    db.query(VM)
                    .filter(VM.project_id == project.id, VM.role == role)
                    .first()
                )

                if vm:
                    vm.status = "provisioned"
                    if vm_name in external_ips:
                        vm.external_ip = external_ips[vm_name]
                    if vm_name in internal_ips:
                        vm.internal_ip = internal_ips[vm_name]
                else:
                    vm = VM(
                        project_id=project.id,
                        name=f"{self.project_name}-{vm_name}",
                        role=role,
                        machine_type=vm_config.get("machine_type", "e2-medium"),
                        disk_size=vm_config.get("disk_size", 20),
                        status="provisioned",
                        external_ip=external_ips.get(vm_name),
                        internal_ip=internal_ips.get(vm_name),
                    )
                    db.add(vm)

            db.commit()
        finally:
            db.close()

    def mark_vms_configured(self, vm_names: list) -> None:
        """Mark VMs as configured (Ansible completed)."""
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return

            for vm_name in vm_names:
                # Try to find by name or role
                vm = (
                    db.query(VM)
                    .filter(VM.project_id == project.id, VM.name.contains(vm_name))
                    .first()
                )

                if vm:
                    vm.status = "configured"

            db.commit()
        finally:
            db.close()

    def mark_foundation_complete(self) -> None:
        """Mark foundation setup as complete - VMs are running."""
        from cli.database import get_db_session, Project, VM

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return

            # Update all VMs to running
            vms = db.query(VM).filter(VM.project_id == project.id).all()
            for vm in vms:
                if vm.status in ["provisioned", "configured"]:
                    vm.status = "running"

            db.commit()
        finally:
            db.close()

    def mark_deployment_complete(self) -> None:
        """Mark entire deployment as complete - all VMs running."""
        self.mark_foundation_complete()

    def mark_addon_deployed(self, addon_name: str, status: str = "deployed") -> None:
        """Mark a single addon as deployed (no-op, addons table already has this)."""
        pass

    def mark_addons_deployed(self, addon_names: list) -> None:
        """Mark addons as deployed (no-op, addons table already has this)."""
        pass

    def update_from_config(self, project_config) -> None:
        """Update state from project configuration (no-op, tables are source of truth)."""
        pass

    def detect_changes(self, project_config):
        """Detect changes between current config and deployed state."""
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

        if changes["vms"]["added"] or changes["vms"]["removed"]:
            changes["needs_terraform"] = True
            changes["has_changes"] = True
            changes["total_changes"] += len(changes["vms"]["added"]) + len(
                changes["vms"]["removed"]
            )

        return changes, state
