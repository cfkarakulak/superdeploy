"""Core addon system components"""

from .addon import Addon
from .addon_loader import (
    AddonLoader,
    AddonNotFoundError,
    AddonValidationError,
    CircularDependencyError,
)
from .template_merger import TemplateMerger
from .validator import ValidationEngine, ValidationError, ValidationException
from .config_loader import (
    ProjectConfig,
    ConfigLoader,
    VMConfig,
    NetworkConfig,
    AppConfig,
)
from .app_type_registry import app_type_registry, AppTypeConfig, AppTypeRegistry

__all__ = [
    "Addon",
    "AddonLoader",
    "AddonNotFoundError",
    "AddonValidationError",
    "CircularDependencyError",
    "TemplateMerger",
    "ValidationEngine",
    "ValidationError",
    "ValidationException",
    "ProjectConfig",
    "ConfigLoader",
    "VMConfig",
    "NetworkConfig",
    "AppConfig",
    "app_type_registry",
    "AppTypeConfig",
    "AppTypeRegistry",
]
