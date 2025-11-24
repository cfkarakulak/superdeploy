"""
Database Synchronization Module

Syncs actual infrastructure state with database after deployment events.
This ensures the dashboard always reflects the real state of VMs, addons, and apps.
"""

from datetime import datetime
from typing import Dict, List, Optional
from cli.database import get_db_session, Project
from sqlalchemy.orm.attributes import flag_modified


def sync_vms(project_name: str, vms: List[Dict[str, str]]) -> None:
    """
    Sync VM actual state to database.

    Args:
        project_name: Name of the project
        vms: List of VM dicts with keys: name, external_ip, internal_ip

    Example:
        sync_vms('cheapa', [
            {'name': 'core-0', 'external_ip': '1.2.3.4', 'internal_ip': '10.1.0.3'},
            {'name': 'app-0', 'external_ip': '5.6.7.8', 'internal_ip': '10.1.0.4'}
        ])
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            print(f"Warning: Project '{project_name}' not found in database")
            return

        actual_state = project.actual_state or {}
        actual_state["vms"] = {}

        for vm in vms:
            actual_state["vms"][vm["name"]] = {
                "external_ip": vm.get("external_ip"),
                "internal_ip": vm.get("internal_ip"),
                "status": "running",
                "updated_at": datetime.utcnow().isoformat(),
            }

        actual_state["last_sync"] = datetime.utcnow().isoformat()
        project.actual_state = actual_state
        flag_modified(project, "actual_state")  # Force SQLAlchemy to detect JSON change
        db.commit()

        print(f"✓ Synced {len(vms)} VMs to database")
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
    Sync addon deployment status to database.

    Args:
        project_name: Name of the project
        addon: Addon identifier (e.g., 'databases.primary', 'caches.primary')
        status: Status (running, stopped, failed, not_deployed)
        container: Container name (optional)
        vm: VM name where addon is deployed (optional)
        health: Health status (healthy, unhealthy) (optional)

    Example:
        sync_addon_status('cheapa', 'databases.primary', 'running',
                         container='cheapa_postgres_primary', vm='core-0', health='healthy')
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        actual_state = project.actual_state or {}
        if "addons" not in actual_state:
            actual_state["addons"] = {}

        addon_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}

        if container:
            addon_data["container"] = container
        if vm:
            addon_data["vm"] = vm
        if health:
            addon_data["health"] = health

        actual_state["addons"][addon] = addon_data
        actual_state["last_sync"] = datetime.utcnow().isoformat()

        project.actual_state = actual_state
        flag_modified(project, "actual_state")  # Force SQLAlchemy to detect JSON change
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

    Example:
        sync_app_status('cheapa', 'api', 'running', containers=2)
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        actual_state = project.actual_state or {}
        if "apps" not in actual_state:
            actual_state["apps"] = {}

        actual_state["apps"][app] = {
            "status": status,
            "containers": containers,
            "updated_at": datetime.utcnow().isoformat(),
        }

        actual_state["last_sync"] = datetime.utcnow().isoformat()
        project.actual_state = actual_state
        flag_modified(project, "actual_state")  # Force SQLAlchemy to detect JSON change
        db.commit()
    finally:
        db.close()


def clear_actual_state(project_name: str) -> None:
    """
    Clear all actual state for a project (used during down/destroy).

    Args:
        project_name: Name of the project

    Example:
        clear_actual_state('cheapa')
    """
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            return

        project.actual_state = {
            "vms": {},
            "addons": {},
            "apps": {},
            "last_sync": datetime.utcnow().isoformat(),
            "status": "terminated",
        }
        flag_modified(project, "actual_state")  # Force SQLAlchemy to detect JSON change
        db.commit()

        print(f"✓ Cleared actual state for project '{project_name}'")
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

        actual_state = project.actual_state or {}
        if "vms" in actual_state and vm_name in actual_state["vms"]:
            actual_state["vms"][vm_name]["status"] = "terminated"
            actual_state["vms"][vm_name]["updated_at"] = datetime.utcnow().isoformat()

            actual_state["last_sync"] = datetime.utcnow().isoformat()
            project.actual_state = actual_state
            flag_modified(
                project, "actual_state"
            )  # Force SQLAlchemy to detect JSON change
            db.commit()
    finally:
        db.close()
