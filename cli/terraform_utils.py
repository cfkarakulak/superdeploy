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
    args: list,
    cwd: Optional[Path] = None,
    capture_output: bool = False
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
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        raise TerraformError(
            f"Terraform command failed: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Error: {e.stderr if capture_output else 'See output above'}"
        )


def list_workspaces() -> list[str]:
    """
    List all Terraform workspaces
    
    Returns:
        List of workspace names (excluding 'default')
    """
    result = run_terraform_command(
        ["workspace", "list"],
        capture_output=True
    )
    
    workspaces = []
    for line in result.stdout.split('\n'):
        # Remove asterisk and whitespace
        workspace = line.strip().replace('*', '').strip()
        if workspace and workspace != 'default':
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
        # Use select -or-create to create if needed
        click.echo(f"Selecting/creating Terraform workspace: {project_name}")
        run_terraform_command(
            ["workspace", "select", "-or-create", project_name]
        )
    else:
        # Just select, will fail if doesn't exist
        click.echo(f"Selecting Terraform workspace: {project_name}")
        run_terraform_command(
            ["workspace", "select", project_name]
        )


def generate_tfvars(
    project_config: ProjectConfig,
    output_file: Optional[Path] = None
) -> Path:
    """
    Generate Terraform variables file from project configuration
    
    Args:
        project_config: Loaded project configuration
        output_file: Optional output file path (defaults to {project_name}.tfvars.json)
        
    Returns:
        Path to generated tfvars file
    """
    if output_file is None:
        terraform_dir = get_terraform_dir()
        output_file = terraform_dir / f"{project_config.project_name}.tfvars.json"
    
    # Get Terraform variables from project config
    tfvars = project_config.to_terraform_vars()
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(tfvars, f, indent=2)
    
    click.echo(f"Generated Terraform variables: {output_file}")
    return output_file


def terraform_init():
    """
    Initialize Terraform (download providers, etc.)
    """
    click.echo("Initializing Terraform...")
    run_terraform_command(["init"])


def terraform_plan(
    project_name: str,
    project_config: ProjectConfig,
    var_file: Optional[Path] = None
):
    """
    Run Terraform plan for a project
    
    Args:
        project_name: Name of the project
        project_config: Loaded project configuration
        var_file: Optional path to tfvars file (will be generated if not provided)
    """
    # Select workspace
    select_workspace(project_name, create=True)
    
    # Generate tfvars if not provided
    if var_file is None:
        var_file = generate_tfvars(project_config)
    
    # Run plan
    click.echo(f"\nRunning Terraform plan for project: {project_name}")
    run_terraform_command(
        ["plan", f"-var-file={var_file}"]
    )


def terraform_apply(
    project_name: str,
    project_config: ProjectConfig,
    var_file: Optional[Path] = None,
    auto_approve: bool = False
):
    """
    Run Terraform apply for a project
    
    Args:
        project_name: Name of the project
        project_config: Loaded project configuration
        var_file: Optional path to tfvars file (will be generated if not provided)
        auto_approve: Whether to skip confirmation prompt
    """
    # Select workspace
    select_workspace(project_name, create=True)
    
    # Generate tfvars if not provided
    if var_file is None:
        var_file = generate_tfvars(project_config)
    
    # Build command
    args = ["apply", f"-var-file={var_file}"]
    if auto_approve:
        args.append("-auto-approve")
    
    # Run apply
    click.echo(f"\nApplying Terraform configuration for project: {project_name}")
    run_terraform_command(args)


def terraform_destroy(
    project_name: str,
    project_config: ProjectConfig,
    var_file: Optional[Path] = None,
    auto_approve: bool = False
):
    """
    Run Terraform destroy for a project
    
    Args:
        project_name: Name of the project
        project_config: Loaded project configuration
        var_file: Optional path to tfvars file (will be generated if not provided)
        auto_approve: Whether to skip confirmation prompt
    """
    # Select workspace
    select_workspace(project_name, create=False)
    
    # Generate tfvars if not provided
    if var_file is None:
        var_file = generate_tfvars(project_config)
    
    # Build command
    args = ["destroy", f"-var-file={var_file}"]
    if auto_approve:
        args.append("-auto-approve")
    
    # Run destroy
    click.echo(f"\nDestroying Terraform infrastructure for project: {project_name}")
    run_terraform_command(args)


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
    result = run_terraform_command(
        ["output", "-json"],
        capture_output=True
    )
    
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
    # Select workspace
    select_workspace(project_name, create=False)
    
    # Generate tfvars
    var_file = generate_tfvars(project_config)
    
    # Run refresh
    click.echo(f"\nRefreshing Terraform state for project: {project_name}")
    run_terraform_command(
        ["refresh", f"-var-file={var_file}"]
    )
