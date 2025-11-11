"""
Deployment State Models

Dataclass models for deployment state management.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class VMStatus(Enum):
    """Status of a VM in deployment lifecycle."""

    PENDING = "pending"
    PROVISIONED = "provisioned"
    CONFIGURED = "configured"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class AddonStatus(Enum):
    """Status of an addon in deployment lifecycle."""

    PENDING = "pending"
    INSTALLING = "installing"
    INSTALLED = "installed"
    DEPLOYED = "deployed"
    ERROR = "error"


class AppStatus(Enum):
    """Status of an app in deployment lifecycle."""

    PENDING = "pending"
    GENERATED = "generated"
    DEPLOYED = "deployed"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class VMState:
    """State of a single VM."""

    name: str
    machine_type: str
    disk_size: int
    services: list[str] = field(default_factory=list)
    status: VMStatus = VMStatus.PENDING
    external_ip: Optional[str] = None
    internal_ip: Optional[str] = None
    provisioned_at: Optional[str] = None
    configured_at: Optional[str] = None

    @property
    def is_provisioned(self) -> bool:
        """Check if VM is provisioned."""
        return self.status in [
            VMStatus.PROVISIONED,
            VMStatus.CONFIGURED,
            VMStatus.RUNNING,
        ]

    @property
    def is_running(self) -> bool:
        """Check if VM is running."""
        return self.status == VMStatus.RUNNING

    @property
    def has_ip(self) -> bool:
        """Check if VM has external IP."""
        return self.external_ip is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "machine_type": self.machine_type,
            "disk_size": self.disk_size,
            "services": self.services,
            "status": self.status.value,
            "external_ip": self.external_ip,
            "internal_ip": self.internal_ip,
            "provisioned_at": self.provisioned_at,
            "configured_at": self.configured_at,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "VMState":
        """Create from dictionary."""
        return cls(
            name=name,
            machine_type=data.get("machine_type", ""),
            disk_size=data.get("disk_size", 20),
            services=data.get("services", []),
            status=VMStatus(data.get("status", "pending")),
            external_ip=data.get("external_ip"),
            internal_ip=data.get("internal_ip"),
            provisioned_at=data.get("provisioned_at"),
            configured_at=data.get("configured_at"),
        )

    def __repr__(self) -> str:
        return f"VMState(name={self.name}, status={self.status.value}, ip={self.external_ip})"


@dataclass
class AddonState:
    """State of a single addon."""

    name: str
    status: AddonStatus = AddonStatus.PENDING
    deployed_at: Optional[str] = None

    @property
    def is_deployed(self) -> bool:
        """Check if addon is deployed."""
        return self.status == AddonStatus.DEPLOYED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "deployed_at": self.deployed_at,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "AddonState":
        """Create from dictionary."""
        return cls(
            name=name,
            status=AddonStatus(data.get("status", "pending")),
            deployed_at=data.get("deployed_at"),
        )

    def __repr__(self) -> str:
        return f"AddonState(name={self.name}, status={self.status.value})"


@dataclass
class AppState:
    """State of a single application."""

    name: str
    path: str
    vm: str
    status: AppStatus = AppStatus.PENDING
    workflows_generated: bool = False
    deployed_at: Optional[str] = None

    @property
    def is_deployed(self) -> bool:
        """Check if app is deployed."""
        return self.status in [AppStatus.DEPLOYED, AppStatus.RUNNING]

    @property
    def is_running(self) -> bool:
        """Check if app is running."""
        return self.status == AppStatus.RUNNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "vm": self.vm,
            "status": self.status.value,
            "workflows_generated": self.workflows_generated,
            "deployed_at": self.deployed_at,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "AppState":
        """Create from dictionary."""
        return cls(
            name=name,
            path=data.get("path", ""),
            vm=data.get("vm", ""),
            status=AppStatus(data.get("status", "pending")),
            workflows_generated=data.get("workflows_generated", False),
            deployed_at=data.get("deployed_at"),
        )

    def __repr__(self) -> str:
        return f"AppState(name={self.name}, status={self.status.value}, vm={self.vm})"


@dataclass
class DeploymentState:
    """Complete deployment state for a project."""

    project_name: str
    vms: Dict[str, VMState] = field(default_factory=dict)
    addons: Dict[str, AddonState] = field(default_factory=dict)
    apps: Dict[str, AppState] = field(default_factory=dict)
    foundation_complete: bool = False
    deployment_complete: bool = False
    last_applied: Optional[str] = None
    config_hash: Optional[str] = None
    secrets_hash: Optional[str] = None
    secrets_last_sync: Optional[str] = None

    @property
    def has_vms(self) -> bool:
        """Check if state has any VMs."""
        return len(self.vms) > 0

    @property
    def has_addons(self) -> bool:
        """Check if state has any addons."""
        return len(self.addons) > 0

    @property
    def has_apps(self) -> bool:
        """Check if state has any apps."""
        return len(self.apps) > 0

    @property
    def is_deployed(self) -> bool:
        """Check if project is fully deployed."""
        return self.deployment_complete and self.has_vms

    def get_vm(self, name: str) -> Optional[VMState]:
        """Get VM state by name."""
        return self.vms.get(name)

    def get_addon(self, name: str) -> Optional[AddonState]:
        """Get addon state by name."""
        return self.addons.get(name)

    def get_app(self, name: str) -> Optional[AppState]:
        """Get app state by name."""
        return self.apps.get(name)

    def get(self, key: str, default=None):
        """
        Dict-style get method for backward compatibility.
        Maps to to_dict() implementation.
        """
        data = self.to_dict()
        return data.get(key, default)

    def __getitem__(self, key: str):
        """Dict-style access for backward compatibility."""
        data = self.to_dict()
        return data[key]

    def __contains__(self, key: str) -> bool:
        """Dict-style 'in' operator for backward compatibility."""
        data = self.to_dict()
        return key in data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {}

        if self.vms:
            result["vms"] = {name: vm.to_dict() for name, vm in self.vms.items()}

        if self.addons:
            result["addons"] = {
                name: addon.to_dict() for name, addon in self.addons.items()
            }

        if self.apps:
            result["apps"] = {name: app.to_dict() for name, app in self.apps.items()}

        if self.foundation_complete or self.deployment_complete:
            result["deployment"] = {
                "foundation_complete": self.foundation_complete,
                "complete": self.deployment_complete,
            }

        if self.last_applied or self.config_hash:
            result["last_applied"] = {
                "timestamp": self.last_applied,
                "config_hash": self.config_hash,
            }

        if self.secrets_hash or self.secrets_last_sync:
            result["secrets"] = {
                "hash": self.secrets_hash,
                "last_sync": self.secrets_last_sync,
            }

        return result

    @classmethod
    def from_dict(cls, project_name: str, data: Dict[str, Any]) -> "DeploymentState":
        """Create from dictionary."""
        vms = {
            name: VMState.from_dict(name, vm_data)
            for name, vm_data in data.get("vms", {}).items()
        }

        addons = {
            name: AddonState.from_dict(name, addon_data)
            for name, addon_data in data.get("addons", {}).items()
        }

        apps = {
            name: AppState.from_dict(name, app_data)
            for name, app_data in data.get("apps", {}).items()
        }

        deployment = data.get("deployment", {})
        last_applied = data.get("last_applied", {})
        secrets = data.get("secrets", {})

        return cls(
            project_name=project_name,
            vms=vms,
            addons=addons,
            apps=apps,
            foundation_complete=deployment.get("foundation_complete", False),
            deployment_complete=deployment.get("complete", False),
            last_applied=last_applied.get("timestamp"),
            config_hash=last_applied.get("config_hash"),
            secrets_hash=secrets.get("hash"),
            secrets_last_sync=secrets.get("last_sync"),
        )

    def __repr__(self) -> str:
        return f"DeploymentState(project={self.project_name}, vms={len(self.vms)}, addons={len(self.addons)}, apps={len(self.apps)})"
