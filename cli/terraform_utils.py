"""Terraform utilities for multi-project support"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import click

from .core.config_loader import ProjectConfig
from .utils import get_project_root


class TerraformError(Exception):
    """Raised when Terraform operations fail"""

    pass


def get_terraform_dir() -> Path:
    """Get the Terraform directory path"""
    return get_project_root() / "shared" / "terraform"


def run_terraform_command(
    args: list, cwd: Optional[Path] = None, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """
    Run a Terraform command

    Args:
        args: Command arguments (e.g., ['workspace', 'list'])
        cwd: Working directory (defaults to terraform dir)
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess instance

    Raises:
        TerraformError: If command fails
    """
    if cwd is None:
        cwd = get_terraform_dir()

    cmd = ["terraform"] + args

    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=capture_output, text=True, check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        error_msg = (
            f"Terraform command failed: {' '.join(cmd)}\nExit code: {e.returncode}\n"
        )
        if capture_output and e.stderr:
            error_msg += f"Error:\n{e.stderr}"
        else:
            error_msg += "Error: Check terraform output above"
        raise TerraformError(error_msg)


def list_workspaces() -> list[str]:
    """
    List all Terraform workspaces

    Returns:
        List of workspace names (excluding 'default')
    """
    result = run_terraform_command(["workspace", "list"], capture_output=True)

    workspaces = []
    for line in result.stdout.split("\n"):
        # Remove asterisk and whitespace
        workspace = line.strip().replace("*", "").strip()
        if workspace and workspace != "default":
            workspaces.append(workspace)

    return workspaces


def workspace_exists(project_name: str) -> bool:
    """
    Check if a workspace exists for a project

    Args:
        project_name: Name of the project

    Returns:
        True if workspace exists, False otherwise
    """
    workspaces = list_workspaces()
    return project_name in workspaces


def workspace_exists(workspace_name: str) -> bool:
    """
    Check if a Terraform workspace exists

    Args:
        workspace_name: Name of the workspace to check

    Returns:
        True if workspace exists, False otherwise
    """
    import subprocess

    terraform_dir = get_terraform_dir()

    try:
        result = subprocess.run(
            ["terraform", "workspace", "list"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse workspace list (format: "  workspace1\n* workspace2\n  workspace3")
        workspaces = [
            line.strip().lstrip("*").strip()
            for line in result.stdout.split("\n")
            if line.strip()
        ]
        return workspace_name in workspaces
    except subprocess.CalledProcessError:
        return False


def select_workspace(project_name: str, create: bool = False):
    """
    Select a Terraform workspace

    Args:
        project_name: Name of the project (workspace name)
        create: Whether to create workspace if it doesn't exist

    Raises:
        TerraformError: If workspace doesn't exist and create=False
    """
    if create:
        # Use select -or-create to create if needed (suppress output)
        run_terraform_command(
            ["workspace", "select", "-or-create", project_name], capture_output=True
        )
    else:
        # Check if workspace exists first
        if not workspace_exists(project_name):
            raise click.ClickException(f"Workspace '{project_name}' does not exist")

        # Just select (suppress output)
        run_terraform_command(
            ["workspace", "select", project_name], capture_output=True
        )


def generate_tfvars(
    project_config: ProjectConfig,
    output_file: Optional[Path] = None,
    preserve_ip: bool = False,
) -> Path:
    """
    Generate Terraform variables file from project configuration

    Args:
        project_config: Loaded project configuration
        output_file: Optional output file path (defaults to {project_name}.tfvars.json)
        preserve_ip: Whether to preserve existing static IPs

    Returns:
        Path to generated tfvars file
    """
    if output_file is None:
        terraform_dir = get_terraform_dir()
        output_file = terraform_dir / f"{project_config.project_name}.tfvars.json"

    # Get Terraform variables from project config
    tfvars = project_config.to_terraform_vars(preserve_ip=preserve_ip)

    # Write to file
    with open(output_file, "w") as f:
        json.dump(tfvars, f, indent=2)

    # Don't print - logger will handle this
    return output_file


def terraform_init(quiet: bool = False):
    """
    Initialize Terraform (download providers, etc.)

    Args:
        quiet: If True, suppress output
    """
    if not quiet:
        click.echo("Initializing Terraform...")
    run_terraform_command(["init"], capture_output=quiet)


def get_terraform_outputs(project_name: str) -> Dict[str, Any]:
    """
    Get Terraform outputs for a project

    Args:
        project_name: Name of the project

    Returns:
        Dictionary of Terraform outputs
    """
    # Select workspace
    select_workspace(project_name, create=False)

    # Get outputs as JSON
    result = run_terraform_command(["output", "-json"], capture_output=True)

    if result.stdout:
        return json.loads(result.stdout)
    return {}


def terraform_refresh(project_name: str, project_config: ProjectConfig):
    """
    Refresh Terraform state for a project

    Args:
        project_name: Name of the project
        project_config: Loaded project configuration
    """
    # Workspace should already be selected by caller

    # Generate tfvars
    var_file = generate_tfvars(project_config)

    # Run refresh (capture output to avoid cluttering terminal)
    run_terraform_command(["refresh", f"-var-file={var_file}"], capture_output=True)
