"""
SSH Operations Service

Centralized SSH command execution and connection management using domain models.
"""

import subprocess
import time
from typing import Optional
from dataclasses import dataclass

from cli.models.ssh import SSHConfig, SSHConnection
from cli.models.results import SSHResult
from cli.exceptions import SSHError
from cli.constants import (
    DEFAULT_SSH_KEY_PATH,
    DEFAULT_SSH_USER,
    SSH_CONNECTION_TIMEOUT,
)


@dataclass
class DockerExecOptions:
    """Options for Docker exec command."""

    interactive: bool = False
    tty: bool = False
    user: Optional[str] = None
    workdir: Optional[str] = None


class SSHService:
    """
    Centralized SSH operations service with type-safe models.

    Responsibilities:
    - Execute SSH commands with result tracking
    - Test SSH connectivity
    - Docker operations over SSH
    - Connection management
    """

    def __init__(
        self,
        ssh_key_path: str = DEFAULT_SSH_KEY_PATH,
        ssh_user: str = DEFAULT_SSH_USER,
    ):
        """
        Initialize SSH service.

        Args:
            ssh_key_path: Path to SSH private key
            ssh_user: SSH username
        """
        self.config = SSHConfig(
            key_path=ssh_key_path,
            user=ssh_user,
        )

    def execute_command(
        self,
        host: str,
        command: str,
        capture_output: bool = True,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> SSHResult:
        """
        Execute command over SSH with result tracking.

        Args:
            host: Host IP or hostname
            command: Command to execute
            capture_output: Capture stdout/stderr
            timeout: Command timeout in seconds
            check: Raise exception on non-zero exit

        Returns:
            SSHResult with execution details

        Raises:
            SSHError: If check=True and command fails
        """
        connection = SSHConnection(host=host, config=self.config)

        ssh_cmd = [
            "ssh",
            "-i",
            str(self.config.key_path_expanded),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            f"{self.config.user}@{host}",
            command,
        ]

        start_time = time.time()

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=False,  # We'll handle errors manually
            )
            duration = time.time() - start_time

            ssh_result = SSHResult(
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                host=host,
                command=command,
                duration_seconds=duration,
            )

            if check and ssh_result.is_failure:
                raise SSHError(
                    f"SSH command failed on {host}",
                    context=f"Command: {command}\nOutput: {ssh_result.output}",
                )

            return ssh_result

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            raise SSHError(
                f"SSH command timed out after {timeout}s",
                context=f"Host: {host}, Command: {command}",
            )
        except Exception as e:
            raise SSHError(
                "SSH command execution failed",
                context=f"Host: {host}, Command: {command}, Error: {str(e)}",
            )

    def test_connection(self, host: str, timeout: int = SSH_CONNECTION_TIMEOUT) -> bool:
        """
        Test SSH connection without waiting.

        Args:
            host: Host IP or hostname
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful
        """
        try:
            result = self.execute_command(host, "echo ok", timeout=timeout)
            return result.is_success
        except Exception:
            return False

    def wait_for_connection(
        self,
        host: str,
        max_attempts: int = 18,
        retry_delay: int = 10,
        timeout: int = SSH_CONNECTION_TIMEOUT,
    ) -> bool:
        """
        Wait for SSH connection to become available.

        Args:
            host: Host IP or hostname
            max_attempts: Maximum connection attempts
            retry_delay: Delay between attempts in seconds
            timeout: Per-attempt timeout in seconds

        Returns:
            True if connection established
        """
        for attempt in range(1, max_attempts + 1):
            if self.test_connection(host, timeout=timeout):
                return True

            if attempt < max_attempts:
                time.sleep(retry_delay)

        return False

    def docker_logs(
        self,
        host: str,
        container_name: str,
        follow: bool = False,
        tail: int = 100,
        since: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Stream Docker logs over SSH.

        Args:
            host: Host IP or hostname
            container_name: Docker container name
            follow: Follow log output
            tail: Number of lines to tail
            since: Show logs since timestamp (e.g., '2h', '1d')

        Returns:
            Popen process object for streaming
        """
        docker_cmd_parts = ["docker", "logs"]

        if follow:
            docker_cmd_parts.append("-f")

        docker_cmd_parts.extend(["--tail", str(tail)])

        if since:
            docker_cmd_parts.extend(["--since", since])

        docker_cmd_parts.append(container_name)
        docker_cmd = " ".join(docker_cmd_parts) + " 2>&1"

        # Use script command to create pseudo-tty for unbuffered output
        # This fixes buffering without requiring interactive terminal (-tt)
        docker_cmd_wrapped = f"script -q -c '{docker_cmd}' /dev/null"
        
        ssh_cmd = [
            "ssh",
            "-i",
            str(self.config.key_path_expanded),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "LogLevel=QUIET",
            f"{self.config.user}@{host}",
            docker_cmd_wrapped,
        ]

        return subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,  # Use binary mode for better compatibility
            bufsize=0,  # Unbuffered for immediate output
        )

    def docker_exec(
        self,
        host: str,
        container_name: str,
        command: str,
        options: Optional[DockerExecOptions] = None,
    ) -> SSHResult:
        """
        Execute command in Docker container over SSH.

        Args:
            host: Host IP or hostname
            container_name: Docker container name
            command: Command to execute
            options: Docker exec options

        Returns:
            SSHResult with execution details
        """
        if options is None:
            options = DockerExecOptions()

        docker_cmd_parts = ["docker", "exec"]

        if options.interactive:
            docker_cmd_parts.append("-i")

        if options.tty:
            docker_cmd_parts.append("-t")

        if options.user:
            docker_cmd_parts.extend(["-u", options.user])

        if options.workdir:
            docker_cmd_parts.extend(["-w", options.workdir])

        docker_cmd_parts.append(container_name)
        docker_cmd_parts.append(command)
        docker_cmd = " ".join(docker_cmd_parts)

        # For interactive/tty mode, use subprocess.run directly
        if options.interactive or options.tty:
            ssh_cmd = [
                "ssh",
                "-i",
                str(self.config.key_path_expanded),
                "-o",
                "StrictHostKeyChecking=no",
                "-t",
                f"{self.config.user}@{host}",
                docker_cmd,
            ]

            start_time = time.time()
            result = subprocess.run(ssh_cmd)
            duration = time.time() - start_time

            return SSHResult(
                returncode=result.returncode,
                host=host,
                command=docker_cmd,
                duration_seconds=duration,
            )
        else:
            # Use standard execute_command for non-interactive
            return self.execute_command(host, docker_cmd)

    def docker_ps(self, host: str, container_filter: Optional[str] = None) -> SSHResult:
        """
        List Docker containers over SSH.

        Args:
            host: Host IP or hostname
            container_filter: Optional filter (e.g., 'name=myapp')

        Returns:
            SSHResult with container listing
        """
        docker_cmd = "docker ps"

        if container_filter:
            docker_cmd += f" --filter '{container_filter}'"

        docker_cmd += " --format '{{.Names}}\t{{.Status}}'"

        return self.execute_command(host, docker_cmd)

    def clean_known_hosts(self, host: str) -> None:
        """
        Remove host from SSH known_hosts file.

        Args:
            host: Host IP or hostname to remove
        """
        try:
            subprocess.run(
                ["ssh-keygen", "-R", host],
                capture_output=True,
                check=False,
            )
        except Exception:
            # Silently fail - not critical
            pass
