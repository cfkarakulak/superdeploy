"""
SuperDeploy CLI Domain Models

Clean dataclass-based models for type-safe data handling.
"""

from .results import (
    CommandResult,
    ValidationResult,
    ExecutionResult,
    SSHResult,
)
from .deployment import (
    DeploymentState,
    VMState,
    AddonState,
    AppState,
)
from .secrets import (
    SecretConfig,
    AppSecrets,
    SharedSecrets,
)
from .ssh import (
    SSHConfig,
    SSHConnection,
)

__all__ = [
    # Results
    "CommandResult",
    "ValidationResult",
    "ExecutionResult",
    "SSHResult",
    # Deployment
    "DeploymentState",
    "VMState",
    "AddonState",
    "AppState",
    # Secrets
    "SecretConfig",
    "AppSecrets",
    "SharedSecrets",
    # SSH
    "SSHConfig",
    "SSHConnection",
]
