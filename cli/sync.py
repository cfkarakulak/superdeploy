"""
Database Synchronization Module

Syncs actual infrastructure state with database after deployment events.
Updates the proper tables (vms, addons, apps) instead of JSON columns.
"""

from typing import Dict, List, Optional
from cli.database import get_db_session, Project, VM, Addon
from rich.console import Console


def sync_vms(project_name: str, vms: List[Dict[str, str]]) -> None:
    """
    Sync VM state to database (vms table).

    Args:
        project_name: Name of the project
        vms: List of VM dicts with keys: name, external_ip, internal_ip, role

    Example:
        sync_vms('cheapa', [
            {'name': 'core-0', 'external_ip': '1.2.3.4', 'internal_ip': '10.1.0.3', 'role': 'core'},
            {'name': 'app-0', 'external_ip': '5.6.7.8', 'internal_ip': '10.1.0.4', 'role': 'app'}
        ])
    """
    console = Console()
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            console.print(
                f"[yellow]Warning: Project '{project_name}' not found in database[/yellow]"
            )
            return

        for vm_data in vms:
            # Extract role from name if not provided (e.g., 'core-0' -> 'core')
            role = vm_data.get("role")
            if not role and "-" in vm_data["name"]:
                role = vm_data["name"].rsplit("-", 1)[0]

            # Find existing VM by role
            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.role == role)
                .first()
            )

            if vm:
                # Update existing VM
                vm.name = vm_data["name"]
                vm.external_ip = vm_data.get("external_ip")
                vm.internal_ip = vm_data.get("internal_ip")
                vm.status = "running"
            else:
                # Create new VM
                vm = VM(
                    project_id=project.id,
                    name=vm_data["name"],
                    role=role or "app",
                    external_ip=vm_data.get("external_ip"),
                    internal_ip=vm_data.get("internal_ip"),
                    status="running",
                    machine_type=vm_data.get("machine_type", "e2-medium"),
                    disk_size=vm_data.get("disk_size", 20),
                )
                db.add(vm)

        db.commit()
        console.print(f"[dim]  ✓ Synced {len(vms)} VMs to database[/dim]")
    finally:
        db.close()


def sync_addon_status(
    project_name: str,
    addon: str,
    status: str,
    container: Optional[str] = None,
    vm: Optional[str] = None,
    health: Optional[str] = None,
) -> None:
    """
    Sync addon deployment status to database (addons table).

    Args:
        project_name: Name of the project
        addon: Addon identifier (e.g., 'postgres', 'redis')
        status: Status (running, stopped, failed, not_deployed)
        container: Container name (optional)
        vm: VM name where addon is deployed (optional)
        health: Health status (healthy, unhealthy) (optional)
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        # Find addon by type
        addon_record = (
            db.query(Addon)
            .filter(Addon.project_id == project.id, Addon.type == addon)
            .first()
        )

        if addon_record:
            addon_record.status = status
            if vm:
                addon_record.vm = vm
            db.commit()
    finally:
        db.close()


def sync_app_status(
    project_name: str, app: str, status: str, containers: int = 0
) -> None:
    """
    Sync application deployment status to database.

    Args:
        project_name: Name of the project
        app: Application name
        status: Status (running, stopped, failed, not_deployed)
        containers: Number of running containers
    """
    # Apps don't have a status column currently, this is a no-op
    # Could add status to apps table if needed
    pass


def clear_project_state(project_name: str) -> None:
    """
    Clear all state for a project (mark VMs as terminated).

    Args:
        project_name: Name of the project

    Example:
        clear_project_state('cheapa')
    """
    console = Console()
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        # Mark all VMs as terminated
        vms = db.query(VM).filter(VM.project_id == project.id).all()
        for vm in vms:
            vm.status = "terminated"
            vm.external_ip = None
            vm.internal_ip = None

        db.commit()
        console.print(f"[dim]  ✓ Cleared state for project '{project_name}'[/dim]")
    finally:
        db.close()


def sync_vm_removed(project_name: str, vm_name: str) -> None:
    """
    Mark a VM as terminated in database.

    Args:
        project_name: Name of the project
        vm_name: Name of the VM to mark as terminated
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        vm = (
            db.query(VM).filter(VM.project_id == project.id, VM.name == vm_name).first()
        )

        if vm:
            vm.status = "terminated"
            vm.external_ip = None
            vm.internal_ip = None
            db.commit()
    finally:
        db.close()
