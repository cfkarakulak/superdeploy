"""
Result Models

Dataclass models for operation results and command outputs.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class ResultStatus(Enum):
    """Status of an operation result."""

    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    PARTIAL = "partial"


@dataclass
class CommandResult:
    """Result of a CLI command execution."""

    status: ResultStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    exit_code: int = 0

    @property
    def is_success(self) -> bool:
        """Check if command succeeded."""
        return self.status == ResultStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Check if command failed."""
        return self.status == ResultStatus.FAILURE

    def __repr__(self) -> str:
        return f"CommandResult(status={self.status.value}, exit_code={self.exit_code})"


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0

    def add_error(self, error: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)

    def __repr__(self) -> str:
        return f"ValidationResult(valid={self.is_valid}, errors={len(self.errors)}, warnings={len(self.warnings)})"


@dataclass
class ExecutionResult:
    """Result of a command execution (subprocess, SSH, etc.)."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    command: str = ""

    @property
    def is_success(self) -> bool:
        """Check if execution succeeded."""
        return self.returncode == 0

    @property
    def is_failure(self) -> bool:
        """Check if execution failed."""
        return self.returncode != 0

    @property
    def output(self) -> str:
        """Get combined output (stdout + stderr)."""
        return f"{self.stdout}\n{self.stderr}".strip()

    def __repr__(self) -> str:
        return f"ExecutionResult(returncode={self.returncode}, command='{self.command[:50]}...')"


@dataclass
class SSHResult:
    """Result of an SSH command execution."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    host: str = ""
    command: str = ""
    duration_seconds: float = 0.0

    @property
    def is_success(self) -> bool:
        """Check if SSH command succeeded."""
        return self.returncode == 0

    @property
    def is_failure(self) -> bool:
        """Check if SSH command failed."""
        return self.returncode != 0

    @property
    def output(self) -> str:
        """Get combined output (stdout + stderr)."""
        return f"{self.stdout}\n{self.stderr}".strip()

    def __repr__(self) -> str:
        return f"SSHResult(host={self.host}, returncode={self.returncode}, duration={self.duration_seconds:.2f}s)"
