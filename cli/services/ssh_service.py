"""SSH service for executing commands on remote hosts."""

import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Dict

from cli.models.ssh import SSHConfig
from cli.models.results import SSHResult


@dataclass
class DockerExecOptions:
    """Options for docker exec command."""

    interactive: bool = False
    tty: bool = False
    user: Optional[str] = None
    workdir: Optional[str] = None
    env: Dict[str, str] = None

    def __post_init__(self):
        if self.env is None:
            self.env = {}


class SSHService:
    """Service for SSH operations."""

    def __init__(self, config: SSHConfig):
        """
        Initialize SSH service.

        Args:
            config: SSH configuration
        """
        self.config = config

    def execute_command(
        self,
        host: str,
        command: str,
        timeout: Optional[int] = 30,
        capture_output: bool = True,
    ) -> SSHResult:
        """
        Execute command on remote host via SSH.

        Args:
            host: Host IP or hostname
            command: Command to execute
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            SSHResult with execution details
        """
        ssh_cmd = [
            "ssh",
            "-i",
            str(self.config.key_path_expanded),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "LogLevel=QUIET",
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
            )
            duration = time.time() - start_time

            return SSHResult(
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                host=host,
                command=command,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            raise TimeoutError(
                f"SSH command timed out after {timeout}s\nContext: Host: {host}, Command: {command}"
            )
        except Exception as e:
            duration = time.time() - start_time
            raise RuntimeError(
                f"SSH command failed: {e}\nContext: Host: {host}, Command: {command}"
            )

    def docker_logs(
        self,
        host: str,
        container_name: str,
        follow: bool = False,
        tail: int = 100,
        since: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Stream Docker logs over SSH - FULLY UNBUFFERED for real-time output.

        Args:
            host: Host IP or hostname
            container_name: Docker container name
            follow: Follow log output
            tail: Number of lines to show from end
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

        # CRITICAL: Force ZERO buffering with stdbuf
        # -o0 = stdout unbuffered (byte-by-byte)
        # -e0 = stderr unbuffered (byte-by-byte)
        # This is the ONLY way to get instant Docker logs over SSH
        docker_cmd_unbuffered = f"stdbuf -o0 -e0 {docker_cmd}"

        ssh_cmd = [
            "ssh",
            "-i",
            str(self.config.key_path_expanded),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "LogLevel=QUIET",
            f"{self.config.user}@{host}",
            docker_cmd_unbuffered,
        ]

        # Popen with ZERO buffering (bufsize=0)
        return subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,  # ZERO buffering - instant output
            universal_newlines=False,
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

        return self.execute_command(host, docker_cmd, timeout=30)

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
