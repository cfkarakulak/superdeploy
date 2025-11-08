"""Marker file management for app tracking"""

import yaml
from pathlib import Path


class MarkerManager:
    """Manages .superdeploy marker files in app repos"""

    @staticmethod
    def create_marker(
        app_path: Path, project: str, app_name: str, vm_role: str = "app"
    ):
        """
        Create .superdeploy marker file

        This file identifies the app to SuperDeploy and contains
        minimal metadata for remote execution.

        Args:
            app_path: Path to application directory
            project: Project name
            app_name: Application name
            vm_role: VM role (e.g., 'app', 'core') for GitHub runner routing
        """
        marker_file = app_path / ".superdeploy"

        marker_content = {
            "project": project,
            "app": app_name,
            "vm": vm_role,
            "managed_by": "superdeploy",
            "version": "v1",
        }

        with open(marker_file, "w") as f:
            yaml.dump(marker_content, f, default_flow_style=False, sort_keys=False)

        return marker_file
