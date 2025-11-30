"""Service for updating secrets with VM internal IPs for cross-container communication."""

from pathlib import Path
from typing import Dict, Any, Optional

from cli.secret_manager import SecretManager
from cli.state_manager import StateManager
from cli.database import get_db_session, Secret, Project


class SecretIPUpdater:
    """
    Updates database secrets with VM internal IPs for multi-VM architecture.

    Cross-VM container communication works via iptables SNAT rule that converts
    Docker container IPs (172.x.x.x) to host VPC IP (10.x.x.x) for VPC traffic.
    This rule is applied by Ansible docker role during VM setup.

    This allows containers to reach services on other VMs using internal IPs,
    which is more secure than exposing addon ports publicly.
    """

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
        self.secret_mgr = SecretManager(project_root, project_name, "production")
        self.state_mgr = StateManager(project_root, project_name)

    def _get_project_id(self, db) -> Optional[int]:
        """Get project ID from database."""
        project = db.query(Project).filter(Project.name == self.project_name).first()
        return project.id if project else None

    def update_secrets_with_vm_ips(self, env: Dict[str, Any], logger) -> None:
        """
        Auto-update database secrets with VM internal IPs.

        This ensures services like postgres/rabbitmq on core VM can be reached
        from apps on app VM using internal VPC IPs.

        Cross-VM communication works because Ansible applies an iptables SNAT rule
        that converts Docker container IPs (172.x) to host VPC IP (10.x) for VPC traffic.

        Args:
            env: Environment variables dict
            logger: Logger instance
        """
        # Get core VM internal IP
        core_internal_ip = self._get_core_internal_ip(env)
        if not core_internal_ip:
            logger.log("  [yellow]⚠ Could not find core VM internal IP[/yellow]")
            return

        updated = False

        # Update shared secrets (legacy HOST keys)
        updated |= self._update_service_hosts(core_internal_ip, logger)

        # Update addon secrets (new architecture: addon.name.HOST)
        updated |= self._update_addon_hosts(core_internal_ip, logger)

        if updated:
            logger.log("  [dim]✓ Database secrets updated with VM internal IPs[/dim]")

    def _get_core_internal_ip(self, env: Dict[str, Any]) -> Optional[str]:
        """
        Get core VM internal IP from env or state.

        Cross-VM container communication works via iptables SNAT rule
        that converts Docker IPs to host VPC IP for VPC traffic.

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
            vms = state.get("vms", {})

            # Try core-0 format
            core_vm = vms.get("core-0", {})
            core_internal_ip = core_vm.get("internal_ip")

            if not core_internal_ip:
                # Try legacy core format
                core_vm = vms.get("core", {})
                core_internal_ip = core_vm.get("internal_ip")

        return core_internal_ip

    def _update_service_hosts(
        self,
        core_internal_ip: str,
        logger,
    ) -> bool:
        """
        Update service host entries with core VM internal IP.

        Args:
            core_internal_ip: Core VM internal IP
            logger: Logger instance

        Returns:
            True if any updates were made
        """
        updated = False
        db = get_db_session()

        try:
            project_id = self._get_project_id(db)
            if not project_id:
                return False

            for host_key, (default_name, service_name) in self.SERVICE_HOSTS.items():
                # Query existing shared secret
                secret = (
                    db.query(Secret)
                    .filter(
                        Secret.project_id == project_id,
                        Secret.app_id.is_(None),  # Shared secret
                        Secret.key == host_key,
                        Secret.environment == "production",
                    )
                    .first()
                )

                if secret and secret.value != core_internal_ip:
                    old_value = secret.value
                    secret.value = core_internal_ip
                    db.commit()
                    updated = True
                    logger.log(
                        f"  [dim]✓ Updated {service_name} host: {old_value} → {core_internal_ip}[/dim]"
                    )

            return updated
        finally:
            db.close()

    def _update_addon_hosts(self, core_internal_ip: str, logger) -> bool:
        """
        Update addon HOST credentials with core VM internal IP.

        For addons like postgres/rabbitmq deployed on core VM, update their HOST
        to core VM internal IP for cross-VM container communication.

        Cross-VM communication works via iptables SNAT rule applied by Ansible.

        Args:
            core_internal_ip: Core VM internal IP
            logger: Logger instance

        Returns:
            True if any updates were made
        """
        updated = False
        db = get_db_session()

        try:
            project_id = self._get_project_id(db)
            if not project_id:
                return False

            # Addon types that should use core VM IP
            core_addon_types = [
                "postgres",
                "rabbitmq",
                "mongodb",
                "redis",
                "elasticsearch",
            ]

            for addon_type in core_addon_types:
                # Query addon secrets with HOST key for this addon type
                # Format: {addon_type}.{instance_name}.HOST
                host_pattern = f"{addon_type}.%.HOST"

                addon_host_secrets = (
                    db.query(Secret)
                    .filter(
                        Secret.project_id == project_id,
                        Secret.key.like(host_pattern),
                        Secret.source == "addon",
                        Secret.environment == "production",
                    )
                    .all()
                )

                for secret in addon_host_secrets:
                    current_host = secret.value

                    # Extract instance name from key: "postgres.primary.HOST" -> "primary"
                    parts = secret.key.split(".")
                    instance_name = parts[1] if len(parts) >= 3 else "unknown"

                    # Update if not already core internal IP
                    if current_host and current_host != core_internal_ip:
                        old_value = current_host
                        secret.value = core_internal_ip
                        db.commit()
                        updated = True
                        logger.log(
                            f"  [dim]✓ Updated {addon_type}.{instance_name}.HOST: {old_value} → {core_internal_ip}[/dim]"
                        )
                    elif not current_host:
                        # If empty, set to core internal IP
                        secret.value = core_internal_ip
                        db.commit()
                        updated = True
                        logger.log(
                            f"  [dim]✓ Set {addon_type}.{instance_name}.HOST → {core_internal_ip}[/dim]"
                        )

            return updated
        finally:
            db.close()
