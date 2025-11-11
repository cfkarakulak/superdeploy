"""
SSH Configuration Models

Dataclass models for SSH operations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SSHConfig:
    """SSH configuration for connecting to VMs."""

    key_path: str
    user: str
    public_key_path: Optional[str] = None

    @property
    def key_path_expanded(self) -> Path:
        """Get expanded key path (resolves ~)."""
        return Path(self.key_path).expanduser()

    @property
    def public_key_path_expanded(self) -> Optional[Path]:
        """Get expanded public key path (resolves ~)."""
        if self.public_key_path:
            return Path(self.public_key_path).expanduser()
        return None

    @property
    def key_exists(self) -> bool:
        """Check if private key file exists."""
        return self.key_path_expanded.exists()

    @property
    def public_key_exists(self) -> bool:
        """Check if public key file exists."""
        if self.public_key_path_expanded:
            return self.public_key_path_expanded.exists()
        return False

    def __repr__(self) -> str:
        return f"SSHConfig(user={self.user}, key={self.key_path})"


@dataclass
class SSHConnection:
    """SSH connection details for a specific host."""

    host: str
    config: SSHConfig
    port: int = 22

    @property
    def connection_string(self) -> str:
        """Get SSH connection string (user@host)."""
        return f"{self.config.user}@{self.host}"

    @property
    def ssh_command_prefix(self) -> list[str]:
        """Get SSH command prefix for subprocess."""
        return [
            "ssh",
            "-i",
            str(self.config.key_path_expanded),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
            self.connection_string,
        ]

    def build_command(self, remote_command: str) -> list[str]:
        """Build full SSH command with remote command."""
        return self.ssh_command_prefix + [remote_command]

    def __repr__(self) -> str:
        return f"SSHConnection(host={self.host}, user={self.config.user})"
