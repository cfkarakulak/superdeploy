"""
Ansible Utilities

Modern Ansible operations manager with type-safe configuration.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class AnsibleExtraVars:
    """Extra variables for Ansible playbook execution."""

    project_name: str
    project_config: Dict[str, Any] = field(default_factory=dict)
    project_secrets: Dict[str, Any] = field(default_factory=dict)
    env_aliases: Dict[str, Any] = field(default_factory=dict)
    addons_source_path: Optional[str] = None
    network_subnet: str = "172.30.0.0/24"
    monitoring_enabled: bool = False
    prometheus_enabled: bool = False
    grafana_enabled: bool = False
    github_org: Optional[str] = None
    orchestrator_ip: Optional[str] = None
    orchestrator_subnet: str = (
        "10.0.0.0/16"  # Default orchestrator subnet for VPC peering
    )
    enabled_addons: Optional[List[str]] = None
    custom_vars: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for Ansible.

        Returns:
            Dictionary with all variables
        """
        result = {
            "project_name": self.project_name,
            "project_config": self.project_config,
            "project_secrets": self.project_secrets,
            "env_aliases": self.env_aliases,
            "network_subnet": self.network_subnet,
            "monitoring_enabled": self.monitoring_enabled,
            "prometheus_enabled": self.prometheus_enabled,
            "grafana_enabled": self.grafana_enabled,
        }

        if self.addons_source_path:
            result["addons_source_path"] = self.addons_source_path

        if self.github_org:
            result["github_org"] = self.github_org

        if self.orchestrator_ip:
            result["orchestrator_ip"] = self.orchestrator_ip

        # Always include orchestrator_subnet for UFW and monitoring rules
        result["orchestrator_subnet"] = self.orchestrator_subnet

        if self.enabled_addons:
            result["enabled_addons"] = self.enabled_addons

        # Add custom vars
        result.update(self.custom_vars)

        return result


@dataclass
class AnsibleCommandOptions:
    """Options for Ansible command execution."""

    tags: Optional[str] = None
    ask_become_pass: bool = False
    force: bool = False
    playbook: Optional[str] = None
    inventory_file: Optional[str] = None
    private_key_path: Optional[str] = None


class AnsibleSerializer:
    """Custom JSON serializer for Ansible extra vars."""

    @staticmethod
    def serialize(obj: Any) -> str:
        """
        Serialize object to JSON with custom handlers.

        Args:
            obj: Object to serialize

        Returns:
            JSON string
        """
        return json.dumps(obj, default=AnsibleSerializer._default)

    @staticmethod
    def _default(obj: Any) -> str:
        """Custom serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")


class AnsibleManager:
    """
    Manages Ansible operations with clean interfaces.

    Responsibilities:
    - Build extra vars from project config
    - Generate Ansible commands
    - Manage inventory files
    - Handle playbook execution
    """

    def __init__(self, project_root: Path, ansible_dir: Optional[Path] = None):
        """
        Initialize Ansible manager.

        Args:
            project_root: Path to superdeploy root directory
            ansible_dir: Path to ansible directory (defaults to shared/ansible)
        """
        self.project_root = project_root
        self.ansible_dir = ansible_dir or (project_root / "shared" / "ansible")

    def generate_extra_vars(
        self,
        project_config: Dict[str, Any],
        project_name: str,
        env_vars: Optional[Dict[str, str]] = None,
        orchestrator_ip: Optional[str] = None,
        enabled_addons: Optional[List[str]] = None,
    ) -> AnsibleExtraVars:
        """
        Generate Ansible extra vars from project configuration.

        Args:
            project_config: Project configuration from ConfigLoader.to_ansible_vars()
            project_name: Name of the project
            env_vars: Optional environment variables to include
            orchestrator_ip: Optional orchestrator IP address
            enabled_addons: Optional list of addons to enable

        Returns:
            AnsibleExtraVars object
        """
        # Extract network config
        network_config = project_config.get("network_config", {})
        network_subnet = network_config.get("docker_subnet", "172.30.0.0/24")

        # Extract monitoring config
        monitoring_config = project_config.get("monitoring", {})
        monitoring_enabled = monitoring_config.get("enabled", False)
        prometheus_enabled = monitoring_config.get("prometheus", False)
        grafana_enabled = monitoring_config.get("grafana", False)

        # Extract GitHub config
        github_org = None
        if project_config.get("project_config", {}).get("github"):
            github_org = project_config["project_config"]["github"].get("organization")

        # Load project secrets
        project_secrets = project_config.get("project_secrets", {})
        if not project_secrets:
            project_secrets = self._load_project_secrets(project_name)

        env_aliases = project_config.get("env_aliases", {})

        # Create extra vars
        extra_vars = AnsibleExtraVars(
            project_name=project_name,
            project_config=project_config,
            project_secrets=project_secrets,
            env_aliases=env_aliases,
            addons_source_path=str(self.project_root / "addons"),
            network_subnet=network_subnet,
            monitoring_enabled=monitoring_enabled,
            prometheus_enabled=prometheus_enabled,
            grafana_enabled=grafana_enabled,
            github_org=github_org,
            orchestrator_ip=orchestrator_ip,
            enabled_addons=enabled_addons,
        )

        # Add top-level keys from project_config to custom_vars for direct Ansible access
        # This allows Ansible to use {{ network_config }} instead of {{ project_config.network_config }}
        for key in [
            "network_config",
            "apps",
            "monitoring",
            "addon_configs",
            "vm_config",
            "docker",
        ]:
            if key in project_config:
                extra_vars.custom_vars[key] = project_config[key]

        # Also extract nested keys from raw project_config for convenience
        if "project_config" in project_config and isinstance(
            project_config["project_config"], dict
        ):
            raw_config = project_config["project_config"]
            for key in ["docker", "github", "project", "addons", "cloud", "vms"]:
                if key in raw_config:
                    extra_vars.custom_vars[key] = raw_config[key]

        # Add environment variables if provided (these override config values)
        if env_vars:
            for key, value in env_vars.items():
                if value:  # Only add non-empty values
                    extra_vars.custom_vars[key] = value

        return extra_vars

    def _load_project_secrets(self, project_name: str) -> Dict[str, Any]:
        """
        Load project secrets from database.

        Args:
            project_name: Name of the project

        Returns:
            Dictionary of secrets
        """
        try:
            from cli.secret_manager import SecretManager

            secret_mgr = SecretManager(self.project_root, project_name, "production")
            if not secret_mgr.has_secrets():
                return {}

            secrets_data = secret_mgr.load_secrets()
            return secrets_data
        except Exception:
            return {}

    def build_command(
        self,
        extra_vars: AnsibleExtraVars,
        options: AnsibleCommandOptions,
    ) -> str:
        """
        Build complete Ansible playbook command.

        Args:
            extra_vars: Extra variables for Ansible
            options: Command options

        Returns:
            Complete ansible-playbook command string
        """
        # Convert extra vars to JSON
        extra_vars_dict = extra_vars.to_dict()
        extra_vars_json = AnsibleSerializer.serialize(extra_vars_dict)
        # Escape single quotes for shell
        extra_vars_json = extra_vars_json.replace("'", "'\\''")

        # Build command parts
        tags_str = f"--tags {options.tags}" if options.tags else ""
        become_pass_str = "--ask-become-pass" if options.ask_become_pass else ""
        force_str = "--flush-cache" if options.force else ""

        # Determine inventory file
        if options.inventory_file:
            inventory_file = options.inventory_file
        else:
            inventory_file = f"inventories/{extra_vars.project_name}.ini"

        # Determine private key path
        if options.private_key_path:
            private_key_path = options.private_key_path
        else:
            import os

            private_key_path = os.path.expanduser(
                os.environ.get("SSH_KEY_PATH", "~/.ssh/superdeploy_deploy")
            )

        private_key_str = (
            f"--private-key {private_key_path}"
            if Path(private_key_path).exists()
            else ""
        )

        # Determine playbook
        playbook = self._determine_playbook(extra_vars.project_name, options.playbook)

        # Get ansible-playbook path from venv
        ansible_playbook_path = self._get_ansible_playbook_path()

        # Build the command
        cmd = f"""
cd {self.ansible_dir} && \\
SUPERDEPLOY_ROOT={self.project_root} {ansible_playbook_path} -i {inventory_file} playbooks/{playbook} {tags_str} {become_pass_str} {force_str} {private_key_str} \\
  --extra-vars '{extra_vars_json}'
"""

        return cmd.strip()

    def _determine_playbook(self, project_name: str, playbook: Optional[str]) -> str:
        """
        Determine which playbook to use.

        Args:
            project_name: Name of the project
            playbook: Optional explicit playbook name

        Returns:
            Playbook filename
        """
        if playbook:
            return playbook

        if project_name == "orchestrator":
            return "orchestrator.yml"
        elif project_name:
            return "project.yml"
        else:
            return "site.yml"

    def _get_ansible_playbook_path(self) -> str:
        """
        Get path to ansible-playbook executable.

        Returns:
            Path to ansible-playbook (venv or system)
        """
        venv_bin = Path(sys.executable).parent
        ansible_playbook_path = venv_bin / "ansible-playbook"

        # Fallback to system ansible-playbook if venv one doesn't exist
        if not ansible_playbook_path.exists():
            return "ansible-playbook"

        return str(ansible_playbook_path)


# Legacy function for backwards compatibility
def build_ansible_command(
    ansible_dir: Path,
    project_root: Path,
    project_config: Dict[str, Any],
    env_vars: Dict[str, str],
    tags: Optional[str] = None,
    project_name: Optional[str] = None,
    ask_become_pass: bool = False,
    enabled_addons: Optional[List[str]] = None,
    playbook: Optional[str] = None,
    force: bool = False,
) -> str:
    """Build Ansible command (legacy)."""
    manager = AnsibleManager(project_root, ansible_dir)

    if not project_name:
        project_name = project_config.get("project_name", "dev")

    extra_vars = manager.generate_extra_vars(
        project_config=project_config,
        project_name=project_name,
        env_vars=env_vars,
        enabled_addons=enabled_addons,
    )

    options = AnsibleCommandOptions(
        tags=tags,
        ask_become_pass=ask_become_pass,
        force=force,
        playbook=playbook,
    )

    return manager.build_command(extra_vars, options)
