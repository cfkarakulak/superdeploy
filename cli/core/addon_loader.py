"""Addon loader with dynamic discovery and dependency resolution"""

from pathlib import Path
from typing import Dict, List
import yaml
from jinja2 import Template

from .addon import Addon


class AddonNotFoundError(Exception):
    """Raised when an addon cannot be found"""

    pass


class AddonValidationError(Exception):
    """Raised when addon metadata is invalid"""

    pass


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected"""

    pass


class AddonLoader:
    """Dynamically loads and validates addons with dependency resolution"""

    def __init__(self, addons_dir: Path):
        """
        Initialize the addon loader.

        Args:
            addons_dir: Path to the addons directory
        """
        self.addons_dir = Path(addons_dir)
        self._addon_cache: Dict[str, Addon] = {}

    def load_addon(self, addon_name: str) -> Addon:
        """
        Load a single addon by name.

        Args:
            addon_name: Name of the addon to load

        Returns:
            Loaded Addon instance

        Raises:
            AddonNotFoundError: If addon directory or required files don't exist
            AddonValidationError: If addon metadata is invalid
        """
        # Return cached addon if available
        if addon_name in self._addon_cache:
            return self._addon_cache[addon_name]

        addon_path = self.addons_dir / addon_name

        # Check if addon directory exists
        if not addon_path.exists() or not addon_path.is_dir():
            raise AddonNotFoundError(f"Addon '{addon_name}' not found at {addon_path}")

        # Load required files
        try:
            metadata = self._load_yaml(addon_path / "addon.yml")
            compose_template = self._load_template(addon_path / "compose.yml.j2")
            env_schema = self._load_yaml(addon_path / "env.yml")
            ansible_tasks = self._load_yaml(addon_path / "ansible.yml")
        except FileNotFoundError as e:
            raise AddonNotFoundError(
                f"Addon '{addon_name}' is missing required file: {e.filename}"
            )
        except yaml.YAMLError as e:
            raise AddonValidationError(f"Addon '{addon_name}' has invalid YAML: {e}")

        # Validate metadata
        self._validate_metadata(addon_name, metadata)

        # Create addon instance
        addon = Addon(
            name=addon_name,
            metadata=metadata,
            compose_template=compose_template,
            env_schema=env_schema,
            ansible_tasks=ansible_tasks,
            addon_path=addon_path,
        )

        # Cache the addon
        self._addon_cache[addon_name] = addon

        return addon

    def load_addons_for_project(self, project_config: dict) -> Dict[str, Addon]:
        """
        Load all addons required by a project, including dependencies.

        Args:
            project_config: Project configuration dictionary

        Returns:
            Dictionary mapping addon names to Addon instances

        Raises:
            AddonNotFoundError: If any required addon is not found
            CircularDependencyError: If circular dependencies are detected
        """
        addons = {}

        # Get addon names from infrastructure section
        # Skip non-addon keys like 'vm_config'
        infrastructure = project_config.get("infrastructure", {})
        non_addon_keys = {"vm_config"}  # These are config, not addons
        for service_name in infrastructure.keys():
            if service_name not in non_addon_keys:
                addon = self.load_addon(service_name)
                addons[service_name] = addon

        # Get addon names from addons section
        addon_configs = project_config.get("addons", {})
        for service_name in addon_configs.keys():
            addon = self.load_addon(service_name)
            addons[service_name] = addon

        # Resolve dependencies
        addons = self._resolve_dependencies(addons)

        return addons

    def _resolve_dependencies(self, addons: Dict[str, Addon]) -> Dict[str, Addon]:
        """
        Recursively resolve addon dependencies.

        Args:
            addons: Initial dictionary of addons

        Returns:
            Dictionary with all addons and their dependencies

        Raises:
            CircularDependencyError: If circular dependencies are detected
        """
        resolved = {}
        visiting = set()

        def resolve(addon_name: str, dependency_chain: List[str]):
            """
            Recursively resolve a single addon and its dependencies.

            Args:
                addon_name: Name of addon to resolve
                dependency_chain: List tracking current dependency chain for cycle detection
            """
            # Already resolved
            if addon_name in resolved:
                return

            # Circular dependency detected
            if addon_name in visiting:
                chain_str = " -> ".join(dependency_chain + [addon_name])
                raise CircularDependencyError(
                    f"Circular dependency detected: {chain_str}"
                )

            # Mark as visiting
            visiting.add(addon_name)

            # Load addon if not already loaded
            addon = addons.get(addon_name)
            if addon is None:
                addon = self.load_addon(addon_name)

            # Resolve dependencies first
            for dep in addon.get_dependencies():
                resolve(dep, dependency_chain + [addon_name])

            # Mark as resolved
            resolved[addon_name] = addon
            visiting.remove(addon_name)

        # Resolve all addons
        for addon_name in list(addons.keys()):
            resolve(addon_name, [])

        return resolved

    def _load_yaml(self, file_path: Path) -> dict:
        """
        Load and parse a YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Parsed YAML as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))

        with open(file_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _load_template(self, file_path: Path) -> Template:
        """
        Load a Jinja2 template file.

        Args:
            file_path: Path to template file

        Returns:
            Jinja2 Template instance

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))

        with open(file_path, "r") as f:
            template_content = f.read()

        return Template(template_content)

    def _validate_metadata(self, addon_name: str, metadata: dict):
        """
        Validate addon metadata structure.

        Args:
            addon_name: Name of the addon
            metadata: Metadata dictionary to validate

        Raises:
            AddonValidationError: If metadata is invalid
        """
        required_fields = ["name", "description", "version"]

        for field in required_fields:
            if field not in metadata:
                raise AddonValidationError(
                    f"Addon '{addon_name}' metadata missing required field: {field}"
                )

        # Validate name matches directory
        if metadata["name"] != addon_name:
            raise AddonValidationError(
                f"Addon '{addon_name}' metadata name '{metadata['name']}' "
                f"doesn't match directory name"
            )
