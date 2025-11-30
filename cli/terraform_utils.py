"""
Terraform Utilities

Modern Terraform operations manager with type-safe models and error handling.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from cli.core.config_loader import ProjectConfig
from cli.utils import get_project_root
from cli.models.results import ExecutionResult
from cli.exceptions import TerraformError


@dataclass
class TerraformOutputs:
    """Terraform outputs with type-safe access."""

    raw_outputs: Dict[str, Any]

    def get_vm_public_ips(self) -> Dict[str, str]:
        """Get VM public IPs from outputs."""
        return self.raw_outputs.get("vm_public_ips", {}).get("value", {})

    def get_vm_internal_ips(self) -> Dict[str, str]:
        """Get VM internal IPs from outputs."""
        return self.raw_outputs.get("vm_internal_ips", {}).get("value", {})

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get output value by key."""
        output = self.raw_outputs.get(key, {})
        return output.get("value", default)


class TerraformManager:
    """
    Manages Terraform operations with clean interfaces.

    Responsibilities:
    - Initialize Terraform
    - Workspace management
    - Apply/destroy operations
    - Output queries
    - tfvars generation
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize Terraform manager.

        Args:
            project_root: Path to superdeploy root (defaults to auto-detect)
        """
        self.project_root = project_root or get_project_root()
        self.terraform_dir = self.project_root / "shared" / "terraform"

    def _run_command(
        self, args: list[str], capture_output: bool = False, check: bool = True
    ) -> ExecutionResult:
        """
        Run Terraform command.

        Args:
            args: Command arguments (e.g., ['workspace', 'list'])
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on failure

        Returns:
            ExecutionResult object

        Raises:
            TerraformError: If command fails and check=True
        """
        cmd = ["terraform"] + args
        cmd_string = " ".join(cmd)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.terraform_dir,
                capture_output=capture_output,
                text=True,
                check=False,
            )

            exec_result = ExecutionResult(
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                command=cmd_string,
            )

            if check and exec_result.is_failure:
                raise TerraformError(
                    f"Terraform command failed: {cmd_string}",
                    context=f"Exit code: {exec_result.returncode}\nError: {exec_result.stderr}",
                )

            return exec_result

        except Exception as e:
            if isinstance(e, TerraformError):
                raise
            raise TerraformError(
                "Failed to execute Terraform command",
                context=f"Command: {cmd_string}, Error: {str(e)}",
            )

    def init(self, upgrade: bool = True, migrate_state: bool = True) -> ExecutionResult:
        """
        Initialize Terraform.

        Args:
            upgrade: Upgrade providers
            migrate_state: Automatically migrate state

        Returns:
            ExecutionResult

        Raises:
            TerraformError: If init fails
        """
        args = ["init", "-input=false", "-no-color"]

        if upgrade:
            args.append("-upgrade")

        if migrate_state:
            args.append("-migrate-state")

        return self._run_command(args, capture_output=True)

    def list_workspaces(self) -> list[str]:
        """
        List all Terraform workspaces.

        Returns:
            List of workspace names (excluding 'default')

        Raises:
            TerraformError: If command fails
        """
        result = self._run_command(["workspace", "list"], capture_output=True)

        workspaces = []
        for line in result.stdout.split("\n"):
            # Remove asterisk and whitespace
            workspace = line.strip().replace("*", "").strip()
            if workspace and workspace != "default":
                workspaces.append(workspace)

        return workspaces

    def workspace_exists(self, workspace_name: str) -> bool:
        """
        Check if workspace exists.

        Args:
            workspace_name: Name of the workspace

        Returns:
            True if workspace exists
        """
        try:
            workspaces = self.list_workspaces()
            # Also check for default workspace
            result = self._run_command(["workspace", "list"], capture_output=True)
            all_workspaces = [
                line.strip().replace("*", "").strip()
                for line in result.stdout.split("\n")
                if line.strip()
            ]
            return workspace_name in all_workspaces
        except Exception:
            return False

    def select_workspace(
        self, workspace_name: str, create: bool = False
    ) -> ExecutionResult:
        """
        Select Terraform workspace.

        Args:
            workspace_name: Name of the workspace
            create: Create workspace if it doesn't exist

        Returns:
            ExecutionResult

        Raises:
            TerraformError: If workspace doesn't exist and create=False
        """
        if create:
            # Use select -or-create to create if needed
            return self._run_command(
                ["workspace", "select", "-or-create", workspace_name],
                capture_output=True,
            )
        else:
            # Check if workspace exists first
            if not self.workspace_exists(workspace_name):
                raise TerraformError(
                    f"Workspace '{workspace_name}' does not exist",
                    context="Use create=True to create automatically",
                )

            # Just select
            return self._run_command(
                ["workspace", "select", workspace_name], capture_output=True
            )

    def generate_tfvars(
        self,
        project_config: ProjectConfig,
        output_file: Optional[Path] = None,
    ) -> Path:
        """
        Generate Terraform variables file from project configuration.

        Args:
            project_config: Project configuration object
            output_file: Output file path (defaults to {project_name}.tfvars.json)

        Returns:
            Path to generated tfvars file
        """
        if output_file is None:
            output_file = (
                self.terraform_dir / f"{project_config.project_name}.tfvars.json"
            )

        # Get Terraform variables from project config
        tfvars = project_config.to_terraform_vars()

        # Write to file
        with open(output_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        return output_file

    def get_outputs(self, workspace_name: str) -> TerraformOutputs:
        """
        Get Terraform outputs for workspace.

        Args:
            workspace_name: Name of the workspace

        Returns:
            TerraformOutputs object

        Raises:
            TerraformError: If command fails
        """
        # Select workspace first
        self.select_workspace(workspace_name, create=False)

        # Get outputs as JSON
        result = self._run_command(["output", "-json"], capture_output=True)

        if result.stdout:
            outputs = json.loads(result.stdout)
            return TerraformOutputs(raw_outputs=outputs)

        return TerraformOutputs(raw_outputs={})

    def refresh(
        self, project_config: ProjectConfig, var_file: Optional[Path] = None
    ) -> ExecutionResult:
        """
        Refresh Terraform state.

        Args:
            project_config: Project configuration
            var_file: Optional path to tfvars file (generates if not provided)

        Returns:
            ExecutionResult

        Raises:
            TerraformError: If refresh fails
        """
        if var_file is None:
            var_file = self.generate_tfvars(project_config)

        return self._run_command(
            ["refresh", f"-var-file={var_file}"], capture_output=True
        )

    def apply(
        self,
        project_config: ProjectConfig,
        var_file: Optional[Path] = None,
        auto_approve: bool = True,
    ) -> ExecutionResult:
        """
        Apply Terraform configuration.

        Args:
            project_config: Project configuration
            var_file: Optional path to tfvars file (generates if not provided)
            auto_approve: Auto-approve changes

        Returns:
            ExecutionResult

        Raises:
            TerraformError: If apply fails
        """
        if var_file is None:
            var_file = self.generate_tfvars(project_config)

        args = ["apply", f"-var-file={var_file}", "-no-color", "-compact-warnings"]

        if auto_approve:
            args.append("-auto-approve")

        return self._run_command(args, capture_output=True)

    def destroy(
        self,
        project_config: ProjectConfig,
        var_file: Optional[Path] = None,
        auto_approve: bool = False,
    ) -> ExecutionResult:
        """
        Destroy Terraform-managed infrastructure.

        Args:
            project_config: Project configuration
            var_file: Optional path to tfvars file (generates if not provided)
            auto_approve: Auto-approve destruction

        Returns:
            ExecutionResult

        Raises:
            TerraformError: If destroy fails
        """
        if var_file is None:
            var_file = self.generate_tfvars(project_config)

        args = ["destroy", f"-var-file={var_file}", "-no-color"]

        if auto_approve:
            args.append("-auto-approve")

        return self._run_command(args, capture_output=True)


# Legacy functions for backwards compatibility
def get_terraform_dir() -> Path:
    """Get the Terraform directory path (legacy)."""
    return TerraformManager().terraform_dir


def select_workspace(project_name: str, create: bool = False):
    """Select workspace (legacy)."""
    manager = TerraformManager()
    manager.select_workspace(project_name, create=create)


def generate_tfvars(
    project_config: ProjectConfig,
    output_file: Optional[Path] = None,
    preserve_ip: bool = False,
) -> Path:
    """Generate tfvars file (legacy).

    Args:
        project_config: Project configuration object
        output_file: Output file path (defaults to {project_name}.tfvars.json)
        preserve_ip: If True, preserve existing VM IP addresses
    """
    manager = TerraformManager()
    return manager.generate_tfvars(project_config, output_file)


def get_terraform_outputs(project_name: str) -> Dict[str, Any]:
    """Get Terraform outputs (legacy)."""
    manager = TerraformManager()
    outputs = manager.get_outputs(project_name)
    return outputs.raw_outputs


def terraform_refresh(project_name: str, project_config: ProjectConfig):
    """Refresh Terraform state (legacy)."""
    manager = TerraformManager()
    manager.select_workspace(project_name, create=False)
    manager.refresh(project_config)


def workspace_exists(workspace_name: str) -> bool:
    """Check if Terraform workspace exists."""
    manager = TerraformManager()
    return manager.workspace_exists(workspace_name)
