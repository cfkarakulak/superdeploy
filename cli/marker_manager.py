"""
Marker File Management

Manages superdeploy marker files for app tracking and identification.

The marker file supports Heroku Procfile-like process definitions with a clean,
minimal syntax. Processes can use Dockerfile commands by default or override them.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from cli.exceptions import ConfigurationError


@dataclass
class ProcessDefinition:
    """
    Represents a single process definition (web, worker, release, etc.).

    Command overrides Dockerfile CMD for flexibility.
    """

    command: str  # Required: the actual command to run
    port: Optional[int] = None
    replicas: int = 1
    run_on: Optional[str] = None  # e.g., "deploy" for release commands
    env: Optional[Dict[str, str]] = None  # Process-specific env vars

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {"command": self.command}

        # Always include replicas (even if default)
        result["replicas"] = self.replicas

        # Include optional fields
        if self.port is not None:
            result["port"] = self.port
        if self.run_on:
            result["run_on"] = self.run_on
        if self.env:
            result["env"] = self.env

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessDefinition":
        """Create from dictionary."""
        return cls(
            command=data.get("command", ""),
            port=data.get("port"),
            replicas=data.get("replicas", 1),
            run_on=data.get("run_on"),
            env=data.get("env"),
        )


@dataclass
class AppMarker:
    """
    Represents superdeploy marker file content.

    Multi-process support (Heroku Procfile-like).
    Each process has command, port, replicas, etc.
    """

    project: str
    app: str
    vm: str

    # Processes as root-level keys (web, worker, release, etc.)
    processes: Dict[str, ProcessDefinition] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """
        Convert to dictionary with clean, minimal syntax.

        Format:
            project: cheapa
            app: api
            vm: app
            web:
              command: python craft serve --host 0.0.0.0 --port 8000
              port: 8000
              replicas: 2
            worker:
              command: python craft queue:work --tries=3
              replicas: 3
        """
        result = {
            "project": self.project,
            "app": self.app,
            "vm": self.vm,
        }

        # Add all processes as root-level keys
        for name, proc_def in self.processes.items():
            result[name] = proc_def.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AppMarker":
        """Create from dictionary."""
        project = data.get("project", "")
        app = data.get("app", "")
        vm = data.get("vm", "app")

        # Parse root-level process keys (web, worker, release, etc.)
        processes = {}
        reserved_keys = {"project", "app", "vm"}

        for key, value in data.items():
            if key not in reserved_keys and isinstance(value, dict):
                processes[key] = ProcessDefinition.from_dict(value)

        return cls(
            project=project,
            app=app,
            vm=vm,
            processes=processes,
        )

    def has_processes(self) -> bool:
        """Check if marker has process definitions."""
        return bool(self.processes)

    def get_process(self, name: str) -> Optional[ProcessDefinition]:
        """Get a specific process definition."""
        return self.processes.get(name)

    def list_processes(self) -> list[str]:
        """List all process names."""
        return list(self.processes.keys())

    def __repr__(self) -> str:
        proc_count = len(self.processes)
        proc_names = ", ".join(self.processes.keys()) if self.processes else "none"
        return f"AppMarker(project={self.project}, app={self.app}, processes=[{proc_names}])"


class MarkerManager:
    """
    Manages superdeploy marker files in app repositories.

    Marker files identify apps to SuperDeploy and contain minimal metadata
    for deployment routing and execution.
    """

    MARKER_FILENAME = "superdeploy"

    @staticmethod
    def create_marker(
        app_path: Path,
        project: str,
        app_name: str,
        vm_role: str = "app",
        processes: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Path:
        """
        Create superdeploy marker file in app directory.

        Args:
            app_path: Path to application directory
            project: Project name
            app_name: Application name
            vm_role: VM role (e.g., 'app', 'core') for GitHub runner routing
            processes: Process definitions dict (required)
                      e.g., {"web": {"command": "...", "port": 8000, "replicas": 2}}

        Returns:
            Path to created marker file

        Raises:
            ConfigurationError: If marker creation fails
        """
        if not app_path.exists():
            raise ConfigurationError(
                f"App path does not exist: {app_path}",
                context="Cannot create marker file in non-existent directory",
            )

        if not processes:
            raise ConfigurationError(
                "Must provide processes dict",
                context="create_marker requires at least one process definition",
            )

        # Parse processes
        process_defs = {}
        for name, proc_data in processes.items():
            process_defs[name] = ProcessDefinition.from_dict(proc_data)

        marker = AppMarker(
            project=project,
            app=app_name,
            vm=vm_role,
            processes=process_defs,
        )

        marker_file = app_path / MarkerManager.MARKER_FILENAME

        try:
            with open(marker_file, "w") as f:
                yaml.dump(
                    marker.to_dict(), f, default_flow_style=False, sort_keys=False
                )
            return marker_file
        except Exception as e:
            raise ConfigurationError(
                "Failed to create marker file",
                context=f"Path: {marker_file}, Error: {str(e)}",
            )

    @staticmethod
    def load_marker(app_path: Path) -> Optional[AppMarker]:
        """
        Load superdeploy marker from app directory.

        Args:
            app_path: Path to application directory

        Returns:
            AppMarker object if file exists, None otherwise

        Raises:
            ConfigurationError: If marker file is invalid
        """
        marker_file = app_path / MarkerManager.MARKER_FILENAME

        if not marker_file.exists():
            return None

        try:
            with open(marker_file, "r") as f:
                data = yaml.safe_load(f) or {}
            return AppMarker.from_dict(data)
        except Exception as e:
            raise ConfigurationError(
                "Failed to load marker file",
                context=f"Path: {marker_file}, Error: {str(e)}",
            )

    @staticmethod
    def has_marker(app_path: Path) -> bool:
        """
        Check if app directory has superdeploy marker file.

        Args:
            app_path: Path to application directory

        Returns:
            True if marker file exists
        """
        marker_file = app_path / MarkerManager.MARKER_FILENAME
        return marker_file.exists()

    @staticmethod
    def validate_marker(app_path: Path) -> bool:
        """
        Validate that marker file exists and is valid.

        Args:
            app_path: Path to application directory

        Returns:
            True if marker is valid

        Raises:
            ConfigurationError: If marker is invalid
        """
        marker = MarkerManager.load_marker(app_path)

        if marker is None:
            raise ConfigurationError(
                "No superdeploy marker found",
                context=f"Path: {app_path}",
            )

        if not marker.project or not marker.app:
            raise ConfigurationError(
                "Invalid marker file - missing required fields",
                context=f"Path: {app_path / MarkerManager.MARKER_FILENAME}",
            )

        return True
