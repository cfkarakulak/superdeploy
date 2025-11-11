"""
App Type Registry - Plugin architecture for supporting different application types.

This module provides a registry for application types (Python, Next.js, etc.) with
pluggable configuration for workflow templates and auto-detection logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class AppTypeConfig:
    """Configuration for an application type."""

    name: str
    workflow_template: str
    detector: Optional[Callable[[Path], bool]] = None
    default_port: Optional[int] = None
    description: str = ""


class AppTypeRegistry:
    """
    Registry for supported application types.

    Provides a centralized, extensible way to manage app type configurations
    including workflow templates and auto-detection logic.
    """

    def __init__(self):
        self._types: dict[str, AppTypeConfig] = {}
        self._register_builtin_types()

    def register(self, config: AppTypeConfig) -> None:
        """Register a new app type."""
        self._types[config.name] = config

    def get(self, app_type: str) -> AppTypeConfig:
        """
        Get app type config.

        Args:
            app_type: The app type name (e.g., "python", "nextjs")

        Returns:
            AppTypeConfig for the requested type

        Raises:
            ValueError: If app type is not registered
        """
        if app_type not in self._types:
            supported = ", ".join(self.list_types())
            raise ValueError(
                f"Unsupported app type: '{app_type}'. Supported types: {supported}"
            )
        return self._types[app_type]

    def list_types(self) -> list[str]:
        """List all registered app type names."""
        return list(self._types.keys())

    def detect(self, app_path: Path) -> str:
        """
        Auto-detect app type from application path.

        Args:
            app_path: Path to the application directory

        Returns:
            Detected app type name, or "unknown" if detection fails
        """
        for app_type, config in self._types.items():
            if config.detector and config.detector(app_path):
                return app_type
        return "unknown"

    def _register_builtin_types(self) -> None:
        """Register built-in app types (Python and Next.js)."""
        # Python applications
        self.register(
            AppTypeConfig(
                name="python",
                workflow_template="github_workflow_python.yml.j2",
                detector=lambda p: (p / "requirements.txt").exists(),
                default_port=8000,
                description="Python application (Django, FastAPI, Cara, etc.)",
            )
        )

        # Next.js applications
        self.register(
            AppTypeConfig(
                name="nextjs",
                workflow_template="github_workflow_nextjs.yml.j2",
                detector=lambda p: (p / "next.config.js").exists()
                or (p / "next.config.ts").exists(),
                default_port=3000,
                description="Next.js application (React-based SSR framework)",
            )
        )


# Global registry instance
app_type_registry = AppTypeRegistry()
