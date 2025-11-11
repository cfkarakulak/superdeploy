"""
Addon Instance Models

Data models for the new addon system supporting multiple named instances.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AddonInstance:
    """Represents a single addon instance (e.g., databases.primary)."""

    category: str  # databases, caches, queues, search, proxy
    name: str  # primary, analytics, session, main
    type: str  # postgres, redis, rabbitmq, elasticsearch, caddy
    version: str  # 15-alpine, 7-alpine, etc.
    plan: str  # small, standard, large, xlarge
    options: Dict = field(default_factory=dict)  # Custom options

    @property
    def full_name(self) -> str:
        """Full instance name: category.name"""
        return f"{self.category}.{self.name}"

    def container_name(self, project: str) -> str:
        """Docker container name: project_type_name"""
        return f"{project}_{self.type}_{self.name}"

    def volume_name(self, project: str) -> str:
        """Docker volume name: project-type-name-data"""
        return f"{project}-{self.type}-{self.name}-data"

    def __repr__(self) -> str:
        return f"AddonInstance({self.full_name}, type={self.type}, plan={self.plan})"


@dataclass
class AddonAttachment:
    """Represents an app → addon attachment."""

    addon: str  # databases.primary (full addon name)
    as_: str  # DATABASE (environment variable prefix)
    access: str = "readwrite"  # readwrite, readonly

    @property
    def category(self) -> str:
        """Extract category from addon reference"""
        return self.addon.split(".")[0]

    @property
    def instance(self) -> str:
        """Extract instance name from addon reference"""
        return self.addon.split(".")[1]

    def __repr__(self) -> str:
        return f"AddonAttachment({self.addon} as {self.as_}, access={self.access})"


@dataclass
class AddonPlan:
    """Resource plan for an addon."""

    name: str  # small, standard, large, xlarge
    memory: str  # 256M, 512M, 1G, 2G
    cpu: str  # 0.25, 0.5, 1.0, 2.0
    disk: Optional[str] = None  # 5G, 10G, 20G, 50G
    max_connections: Optional[int] = None  # For databases
    description: Optional[str] = None

    def __repr__(self) -> str:
        return f"AddonPlan({self.name}, memory={self.memory}, cpu={self.cpu})"
