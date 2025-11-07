"""
SSH Operations Service

Centralized SSH command execution and connection management.
Used by 15+ commands that need SSH access.
"""

import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console
from cli.constants import (
    DEFAULT_SSH_KEY_PATH,
    DEFAULT_SSH_USER,
    SSH_CONNECTION_TIMEOUT,
)

console = Console()


class SSHService:
    """
    Centralized SSH operations service.

    Responsibilities:
    - Execute SSH commands
    - Interactive SSH sessions
    - Wait for SSH availability
    - File upload/download
    """

    def __init__(
        self, ssh_key_path: str = DEFAULT_SSH_KEY_PATH, ssh_user: str = DEFAULT_SSH_USER
    ):
        self.ssh_key_path = Path(ssh_key_path).expanduser()
        self.ssh_user = ssh_user

    def execute_command(
        self,
        host: str,
        command: str,
        capture_output: bool = True,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        Execute command over SSH.

        Args:
            host: Host IP or hostname
            command: Command to execute
            capture_output: Capture stdout/stderr
            timeout: Command timeout in seconds
            check: Raise exception on non-zero exit

        Returns:
            CompletedProcess object
        """
        ssh_cmd = [
            "ssh",
            "-i",
            str(self.ssh_key_path),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            f"{self.ssh_user}@{host}",
            command,
        ]

        return subprocess.run(
            ssh_cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=check,
        )

    def test_connection(self, host: str) -> bool:
        """
        Test SSH connection without waiting.

        Args:
            host: Host IP or hostname

        Returns:
            True if connection successful
        """
        try:
            result = self.execute_command(
                host, "echo ok", timeout=SSH_CONNECTION_TIMEOUT
            )
            return result.returncode == 0
        except Exception:
            return False

    def docker_logs(
        self, host: str, container_name: str, follow: bool = False, tail: int = 100
    ) -> subprocess.Popen:
        """
        Stream Docker logs over SSH.

        Args:
            host: Host IP or hostname
            container_name: Docker container name
            follow: Follow log output
            tail: Number of lines to tail

        Returns:
            Popen process object
        """
        follow_flag = "-f" if follow else ""
        docker_cmd = f"docker logs {follow_flag} --tail {tail} {container_name} 2>&1"

        ssh_cmd = [
            "ssh",
            "-i",
            str(self.ssh_key_path),
            "-o",
            "StrictHostKeyChecking=no",
            f"{self.ssh_user}@{host}",
            docker_cmd,
        ]

        return subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def docker_exec(
        self, host: str, container_name: str, command: str, interactive: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Execute command in Docker container over SSH.

        Args:
            host: Host IP or hostname
            container_name: Docker container name
            command: Command to execute
            interactive: Use interactive mode

        Returns:
            CompletedProcess object
        """
        docker_cmd = (
            f"docker exec {'- it' if interactive else ''} {container_name} {command}"
        )

        if interactive:
            return subprocess.run(
                [
                    "ssh",
                    "-i",
                    str(self.ssh_key_path),
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-t",
                    f"{self.ssh_user}@{host}",
                    docker_cmd,
                ]
            )
        else:
            return self.execute_command(host, docker_cmd)
