"""Service for updating secrets with VM internal IPs."""

from pathlib import Path
from typing import Dict, Any, Optional

from cli.secret_manager import SecretManager
from cli.state_manager import StateManager


class SecretIPUpdater:
    """Updates secrets.yml with VM internal IPs for multi-VM architecture."""

    # Service host mappings
    SERVICE_HOSTS = {
        "POSTGRES_HOST": ("postgres", "PostgreSQL"),
        "RABBITMQ_HOST": ("rabbitmq", "RabbitMQ"),
        "MONGODB_HOST": ("mongodb", "MongoDB"),
        "REDIS_HOST": ("redis", "Redis"),
        "ELASTICSEARCH_HOST": ("elasticsearch", "Elasticsearch"),
    }

    def __init__(self, project_root: Path, project_name: str):
        """
        Initialize IP updater.

        Args:
            project_root: Path to project root
            project_name: Name of the project
        """
        self.project_root = project_root
        self.project_name = project_name
        self.secret_mgr = SecretManager(project_root, project_name)
        self.state_mgr = StateManager(project_root, project_name)

    def update_secrets_with_vm_ips(self, env: Dict[str, Any], logger) -> None:
        """
        Auto-update secrets.yml with VM internal IPs.

        This ensures services like postgres/rabbitmq on core VM can be reached
        from apps on app VM using internal IPs instead of hostnames.

        Args:
            env: Environment variables dict
            logger: Logger instance
        """
        secrets_data = self.secret_mgr.load_secrets()

        if not secrets_data:
            return

        # Get core VM internal IP
        core_internal_ip = self._get_core_internal_ip(env)
        if not core_internal_ip:
            return

        updated = False

        # Update shared secrets (legacy)
        shared_secrets = secrets_data.shared.values
        if shared_secrets:
            updated |= self._update_service_hosts(
                secrets_data, shared_secrets, core_internal_ip, logger
            )

        # Update addon secrets (new architecture)
        if secrets_data.addons:
            updated |= self._update_addon_hosts(
                secrets_data, core_internal_ip, logger
            )

        if updated:
            self.secret_mgr.save_secrets(secrets_data)
            logger.log("  [dim]✓ secrets.yml updated with VM internal IPs[/dim]")

    def _get_core_internal_ip(self, env: Dict[str, Any]) -> Optional[str]:
        """
        Get core VM internal IP from env or state.

        Args:
            env: Environment variables dict

        Returns:
            Core VM internal IP or None
        """
        # Try from environment first
        core_internal_ip = env.get("CORE_0_INTERNAL_IP")

        if not core_internal_ip:
            # Try from state
            state = self.state_mgr.load_state()
            core_vm = state.get("vms", {}).get("core", {})
            core_internal_ip = core_vm.get("internal_ip")

        return core_internal_ip

    def _update_service_hosts(
        self,
        secrets_data: Any,
        shared_secrets: Dict[str, str],
        core_internal_ip: str,
        logger,
    ) -> bool:
        """
        Update service host entries with core VM IP.

        Args:
            secrets_data: Secrets data object
            shared_secrets: Shared secrets dict
            core_internal_ip: Core VM internal IP
            logger: Logger instance

        Returns:
            True if any updates were made
        """
        updated = False

        for host_key, (default_name, service_name) in self.SERVICE_HOSTS.items():
            if host_key in shared_secrets:
                current_value = shared_secrets[host_key]

                # Update if different from core IP
                if current_value != core_internal_ip:
                    old_value = current_value
                    secrets_data.shared.set(host_key, core_internal_ip)
                    updated = True
                    logger.log(
                        f"  [dim]✓ Updated {service_name} host: {old_value} → {core_internal_ip}[/dim]"
                    )

        return updated

    def _update_addon_hosts(
        self, secrets_data: Any, core_internal_ip: str, logger
    ) -> bool:
        """
        Update addon HOST credentials with core VM internal IP.

        For addons like postgres/rabbitmq deployed on core VM, update their HOST
        to core VM internal IP for cross-VM communication.

        Args:
            secrets_data: Secrets data object
            core_internal_ip: Core VM internal IP
            logger: Logger instance

        Returns:
            True if any updates were made
        """
        updated = False

        # Addon types that should use core VM IP
        core_addon_types = ["postgres", "rabbitmq", "mongodb", "redis", "elasticsearch"]

        for addon_type in core_addon_types:
            if addon_type not in secrets_data.addons:
                continue

            addon_instances = secrets_data.addons[addon_type]

            for instance_name, credentials in addon_instances.items():
                if "HOST" in credentials:
                    current_host = credentials["HOST"]

                    # Update if not already core IP and not empty
                    if current_host and current_host != core_internal_ip:
                        old_value = current_host
                        credentials["HOST"] = core_internal_ip
                        updated = True
                        logger.log(
                            f"  [dim]✓ Updated {addon_type}.{instance_name}.HOST: {old_value} → {core_internal_ip}[/dim]"
                        )
                    elif not current_host:
                        # If empty, set to core IP
                        credentials["HOST"] = core_internal_ip
                        updated = True
                        logger.log(
                            f"  [dim]✓ Set {addon_type}.{instance_name}.HOST → {core_internal_ip}[/dim]"
                        )

        return updated
