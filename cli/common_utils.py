"""
CLI Utilities

Core utility functions and classes for SuperDeploy CLI.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from rich.console import Console

from cli.models.results import ValidationResult
from cli.exceptions import ConfigurationError


class ProjectUtils:
    """Utilities for project discovery and validation."""

    @staticmethod
    def get_project_root() -> Path:
        """
        Get SuperDeploy project root directory.

        Returns:
            Path to superdeploy directory (contains projects/, addons/, etc.)
        """
        # Start from current file location and go up to find superdeploy root
        current = Path(__file__).resolve()
        # Go up from cli/utils.py -> cli/ -> superdeploy/
        return current.parent.parent

    @staticmethod
    def get_available_projects() -> List[str]:
        """
        Get list of available projects.

        Returns:
            List of project names
        """
        project_root = ProjectUtils.get_project_root()
        projects_dir = project_root / "projects"

        if not projects_dir.exists():
            return []

        return [
            d.name
            for d in projects_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    @staticmethod
    def validate_project_exists(project_name: str) -> None:
        """
        Validate that project exists.

        Args:
            project_name: Name of the project

        Raises:
            ConfigurationError: If project doesn't exist
        """
        available = ProjectUtils.get_available_projects()

        if not available:
            raise ConfigurationError(
                "No projects found in projects/ directory",
                context="Run: superdeploy <project-name>:init",
            )

        if project_name not in available:
            raise ConfigurationError(
                f"Project '{project_name}' not found",
                context=f"Available projects: {', '.join(available)}",
            )

    @staticmethod
    def get_project_path(project_name: str) -> Path:
        """
        Get project directory path.

        Args:
            project_name: Name of the project

        Returns:
            Path to project directory

        Raises:
            ConfigurationError: If project doesn't exist
        """
        ProjectUtils.validate_project_exists(project_name)
        return ProjectUtils.get_project_root() / "projects" / project_name


class EnvironmentValidator:
    """Validates environment variables and configuration."""

    @staticmethod
    def validate_env_vars(
        env: Dict[str, str], required_keys: List[str]
    ) -> ValidationResult:
        """
        Validate required environment variables are present.

        Args:
            env: Dictionary of environment variables
            required_keys: List of required variable names

        Returns:
            ValidationResult with errors for missing keys
        """
        result = ValidationResult(is_valid=True)
        missing = [key for key in required_keys if not env.get(key)]

        for key in missing:
            result.add_error(f"Missing required environment variable: {key}")

        return result

    @staticmethod
    def print_validation_errors(
        result: ValidationResult, console: Optional[Console] = None
    ) -> None:
        """
        Print validation errors to console.

        Args:
            result: ValidationResult with errors
            console: Rich console (creates new if not provided)
        """
        if console is None:
            console = Console()

        if result.has_errors:
            console.print("[red]✗ Validation failed:[/red]")
            for error in result.errors:
                console.print(f"  • {error}")

        if result.has_warnings:
            console.print("[yellow]⚠ Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  • {warning}")


class CommandExecutor:
    """Executes shell commands with error handling."""

    @staticmethod
    def run_command(
        cmd: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Run shell command with error handling.

        Args:
            cmd: Command string to execute
            cwd: Working directory
            env: Environment variables
            capture_output: Capture stdout/stderr
            check: Raise exception on non-zero exit

        Returns:
            CompletedProcess object

        Raises:
            RuntimeError: If command fails and check=True
        """
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                env={**os.environ, **(env or {})},
                capture_output=capture_output,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed: {cmd}\nExit code: {e.returncode}"
            if e.stderr:
                error_msg += f"\nError: {e.stderr}"
            raise RuntimeError(error_msg)


class SSHCommandBuilder:
    """Builds SSH commands for remote execution."""

    @staticmethod
    def build_command(
        host: str,
        user: str,
        key_path: str,
        remote_cmd: str,
        silent_on_error: bool = False,
    ) -> str:
        """
        Build SSH command string.

        Args:
            host: Remote host IP/hostname
            user: SSH user
            key_path: Path to SSH private key
            remote_cmd: Command to run on remote host
            silent_on_error: If True, suppress error output

        Returns:
            SSH command string
        """
        expanded_key_path = os.path.expanduser(key_path)
        ssh_cmd = (
            f"ssh -i {expanded_key_path} "
            f"-o StrictHostKeyChecking=no "
            f"{user}@{host} '{remote_cmd}'"
        )
        return ssh_cmd

    @staticmethod
    def execute(
        host: str,
        user: str,
        key_path: str,
        remote_cmd: str,
        silent_on_error: bool = False,
    ) -> str:
        """
        Execute SSH command and return output.

        Args:
            host: Remote host IP/hostname
            user: SSH user
            key_path: Path to SSH private key
            remote_cmd: Command to run on remote host
            silent_on_error: If True, raise exception instead of printing error

        Returns:
            Command output as string

        Raises:
            subprocess.CalledProcessError: If silent_on_error=True and command fails
        """
        ssh_cmd = SSHCommandBuilder.build_command(
            host, user, key_path, remote_cmd, silent_on_error
        )

        if silent_on_error:
            result = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        else:
            result = CommandExecutor.run_command(ssh_cmd, capture_output=True)
            return result.stdout.strip()


# Legacy functions for backwards compatibility
def get_project_root() -> Path:
    """Get SuperDeploy project root (legacy)."""
    return ProjectUtils.get_project_root()


def get_available_projects() -> List[str]:
    """Get available projects (legacy)."""
    return ProjectUtils.get_available_projects()


def validate_project(project: str) -> None:
    """Validate project exists (legacy)."""
    console = Console()
    try:
        ProjectUtils.validate_project_exists(project)
    except ConfigurationError as e:
        console.print(f"[red]❌ {e.message}[/red]")
        if e.context:
            console.print(f"[dim]{e.context}[/dim]")
        raise SystemExit(1)


def get_project_path(project: str) -> Path:
    """Get project path (legacy)."""
    return ProjectUtils.get_project_path(project)


def validate_env_vars(env: Dict[str, str], required_keys: List[str]) -> bool:
    """Validate environment variables (legacy)."""
    result = EnvironmentValidator.validate_env_vars(env, required_keys)

    if not result.is_valid:
        EnvironmentValidator.print_validation_errors(result)
        return False

    return True


def run_command(
    cmd: str,
    cwd: Optional[str] = None,
    env: Optional[Dict] = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run command (legacy)."""
    cwd_path = Path(cwd) if cwd else None
    return CommandExecutor.run_command(cmd, cwd_path, env, capture_output)
