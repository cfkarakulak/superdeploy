"""
SSH Operations Service

Centralized SSH command execution and connection management.
Used by 15+ commands that need SSH access.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from cli.constants import (
    DEFAULT_SSH_KEY_PATH,
    DEFAULT_SSH_USER,
    SSH_CONNECTION_TIMEOUT,
    SSH_WAIT_MAX_ATTEMPTS,
    SSH_WAIT_DELAY,
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

    def execute_command_simple(self, host: str, command: str) -> str:
        """
        Execute command and return stdout.

        Args:
            host: Host IP or hostname
            command: Command to execute

        Returns:
            Command stdout

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        result = self.execute_command(host, command, check=True)
        return result.stdout

    def execute_interactive(self, host: str, command: str) -> int:
        """
        Execute command with interactive TTY.

        Args:
            host: Host IP or hostname
            command: Command to execute

        Returns:
            Exit code
        """
        ssh_cmd = [
            "ssh",
            "-i",
            str(self.ssh_key_path),
            "-o",
            "StrictHostKeyChecking=no",
            "-t",
            f"{self.ssh_user}@{host}",
            command,
        ]

        return subprocess.call(ssh_cmd)

    def wait_for_ssh(
        self,
        host: str,
        max_attempts: int = SSH_WAIT_MAX_ATTEMPTS,
        delay: int = SSH_WAIT_DELAY,
        check_sudo: bool = True,
        verbose: bool = False,
    ) -> bool:
        """
        Wait for SSH to become available.

        Args:
            host: Host IP or hostname
            max_attempts: Maximum connection attempts
            delay: Delay between attempts in seconds
            check_sudo: Also verify sudo access
            verbose: Print progress messages

        Returns:
            True if SSH available, False otherwise
        """
        for attempt in range(1, max_attempts + 1):
            if verbose:
                console.print(
                    f"[dim]SSH check attempt {attempt}/{max_attempts}...[/dim]"
                )

            try:
                if check_sudo:
                    # Check both connection and sudo
                    result = self.execute_command(
                        host, "sudo -n whoami", timeout=SSH_CONNECTION_TIMEOUT
                    )

                    if result.returncode == 0 and "root" in result.stdout:
                        if verbose:
                            console.print("[green]✓ SSH ready[/green]")
                        return True
                else:
                    # Just check connection
                    result = self.execute_command(
                        host, "echo ok", timeout=SSH_CONNECTION_TIMEOUT
                    )

                    if result.returncode == 0:
                        if verbose:
                            console.print("[green]✓ SSH ready[/green]")
                        return True

            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass

            if attempt < max_attempts:
                if verbose:
                    console.print(f"[dim]Waiting {delay}s...[/dim]")
                time.sleep(delay)

        return False

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

    def upload_file(self, host: str, local_path: Path, remote_path: str) -> bool:
        """
        Upload file via SCP.

        Args:
            host: Host IP or hostname
            local_path: Local file path
            remote_path: Remote file path

        Returns:
            True if successful
        """
        scp_cmd = [
            "scp",
            "-i",
            str(self.ssh_key_path),
            "-o",
            "StrictHostKeyChecking=no",
            str(local_path),
            f"{self.ssh_user}@{host}:{remote_path}",
        ]

        result = subprocess.run(scp_cmd, capture_output=True)
        return result.returncode == 0

    def download_file(self, host: str, remote_path: str, local_path: Path) -> bool:
        """
        Download file via SCP.

        Args:
            host: Host IP or hostname
            remote_path: Remote file path
            local_path: Local file path

        Returns:
            True if successful
        """
        scp_cmd = [
            "scp",
            "-i",
            str(self.ssh_key_path),
            "-o",
            "StrictHostKeyChecking=no",
            f"{self.ssh_user}@{host}:{remote_path}",
            str(local_path),
        ]

        result = subprocess.run(scp_cmd, capture_output=True)
        return result.returncode == 0

    def clean_known_hosts(self, host: str) -> None:
        """
        Remove host from SSH known_hosts.

        Args:
            host: Host IP or hostname
        """
        subprocess.run(["ssh-keygen", "-R", host], capture_output=True)

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
