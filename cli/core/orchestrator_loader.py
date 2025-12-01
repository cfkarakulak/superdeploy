"""Orchestrator configuration loader - DB-based"""

from pathlib import Path
from typing import Dict, Any, Optional


class OrchestratorConfig:
    """Manages global orchestrator configuration - DB-based"""

    def __init__(self, config_path: Path):
        """
        Initialize orchestrator config from database

        Args:
            config_path: Path to shared dir (legacy parameter, not used)
        """
        self.base_path = (
            config_path.parent.parent if config_path.exists() else Path.cwd() / "shared"
        )
        self.config = self._load_config()
        self.raw_config = self.config

        # Initialize managers
        from cli.core.orchestrator_secret_manager import OrchestratorSecretManager

        self.secret_manager = OrchestratorSecretManager(self.base_path)

    def _load_config(self) -> Dict[str, Any]:
        """Load orchestrator configuration from database ONLY"""
        from cli.database import get_db_session, Project, Addon

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )

            if not db_project:
                raise FileNotFoundError(
                    "Orchestrator not found in database.\n"
                    "Run: superdeploy orchestrator:init"
                )

            # Load addons from database
            db_addons = db.query(Addon).filter(Addon.project_id == db_project.id).all()

            # Build addons structure: {category: {instance_name: {type, version, ...}}}
            addons = {}
            for addon in db_addons:
                if addon.category not in addons:
                    addons[addon.category] = {}
                addons[addon.category][addon.instance_name] = {
                    "type": addon.type,
                    "version": addon.version,
                    "vm": addon.vm,
                    "plan": addon.plan,
                }

            # Build config from database
            config = {
                "gcp": {
                    "project_id": db_project.gcp_project,
                    "region": db_project.gcp_region,
                    "zone": db_project.gcp_zone,
                },
                "ssl": {
                    "email": db_project.ssl_email,
                },
                "ssh": {
                    "key_path": db_project.ssh_key_path or "~/.ssh/superdeploy_deploy",
                    "public_key_path": db_project.ssh_public_key_path
                    or "~/.ssh/superdeploy_deploy.pub",
                    "user": db_project.ssh_user or "superdeploy",
                },
                "network": {
                    "docker_subnet": db_project.docker_subnet,
                    "vpc_subnet": db_project.vpc_subnet,
                },
                "vm": {
                    "name": "orchestrator-main-0",
                    "machine_type": "e2-medium",
                    "disk_size": 50,
                },
                "addons": addons,  # Include addons from DB
            }
            return config
        finally:
            db.close()

    def is_deployed(self) -> bool:
        """Check if orchestrator is already deployed by checking database"""
        from cli.database import get_db_session, Project, Secret, VM

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            if not db_project:
                return False

            # Check if we have an IP stored (means deployed)
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == db_project.id, Secret.key == "ORCHESTRATOR_IP"
                )
                .first()
            )
            if secret and secret.value:
                return True

            # Fallback to VMs table
            vm = (
                db.query(VM)
                .filter(VM.project_id == db_project.id, VM.external_ip.isnot(None))
                .first()
            )
            return vm is not None
        finally:
            db.close()

    def get_ip(self) -> Optional[str]:
        """Get orchestrator IP from database"""
        from cli.database import get_db_session, Project, Secret, VM

        db = get_db_session()
        try:
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            if not db_project:
                return None

            # Try secrets first
            secret = (
                db.query(Secret)
                .filter(
                    Secret.project_id == db_project.id, Secret.key == "ORCHESTRATOR_IP"
                )
                .first()
            )
            if secret and secret.value:
                return secret.value

            # Fallback to VMs table
            vm = (
                db.query(VM)
                .filter(VM.project_id == db_project.id, VM.external_ip.isnot(None))
                .first()
            )
            if vm:
                return vm.external_ip

            return None
        finally:
            db.close()

    def get_vm_config(self) -> Dict[str, Any]:
        """Get VM configuration for orchestrator"""
        return self.config.get("vm", {})

    def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration"""
        return self.config.get("network", {})

    def to_terraform_vars(
        self, project_id: str, ssh_pub_key_path: str
    ) -> Dict[str, Any]:
        """
        Convert to Terraform variables format

        Args:
            project_id: GCP project ID (from config)
            ssh_pub_key_path: Path to SSH public key (from config)

        Returns:
            Dictionary suitable for Terraform tfvars
        """
        vm_config = self.get_vm_config()
        network_config = self.get_network_config()
        gcp_config = self.config.get("gcp", {})

        # Use reserved orchestrator subnet
        from cli.subnet_allocator import SubnetAllocator

        orchestrator_subnet = SubnetAllocator.get_orchestrator_subnet()

        return {
            "project_id": project_id,
            "project_name": "orchestrator",
            "region": gcp_config.get("region", "us-central1"),
            "zone": gcp_config.get("zone", "us-central1-a"),
            "vm_groups": {
                "main-0": {
                    "role": "main",
                    "index": 0,
                    "machine_type": vm_config.get("machine_type", "e2-medium"),
                    "disk_size": vm_config.get("disk_size", 50),
                    "tags": ["main", "orchestrator", "monitoring", "ssh"],
                    "labels": {
                        "role": "orchestrator",
                        "shared": "true",
                    },
                }
            },
            "subnet_cidr": orchestrator_subnet,  # Use reserved subnet
            "network_name": network_config.get("vpc_name", "superdeploy-network"),
            "ssh_pub_key_path": ssh_pub_key_path,
            # Allow all 10.x.x.x subnets for Loki ingestion from project VMs
            "allowed_client_subnets": ["10.0.0.0/8"],
        }

    def get_secrets(self) -> Dict[str, str]:
        """Get all orchestrator secrets"""
        return self.secret_manager.get_all_secrets()

    def get_secret(self, key: str) -> str:
        """Get specific secret"""
        return self.secret_manager.get_secret(key)

    def initialize_secrets(self) -> Dict[str, str]:
        """Initialize secrets if they don't exist"""
        return self.secret_manager.initialize_secrets()

    def to_ansible_vars(self) -> Dict[str, Any]:
        """
        Convert to Ansible variables format

        Returns:
            Dictionary suitable for Ansible extra vars
        """
        # Monitoring is always enabled
        grafana_config = self.config.get("grafana", {})
        prometheus_config = self.config.get("prometheus", {})
        caddy_config = self.config.get("caddy", {})

        enabled_addons = ["monitoring"]
        addon_configs = {
            "monitoring": {"grafana": grafana_config, "prometheus": prometheus_config},
        }

        # Add Caddy if enabled (for monitoring reverse proxy)
        if caddy_config.get("enabled", False):
            enabled_addons.append("caddy")
            addon_configs["caddy"] = caddy_config

        # Get project info for ssl_email
        project_config = self.config.get("project", {})

        # Get network config
        network_config = self.config.get("network", {})

        # Get addons configuration from config file
        addons_config = self.config.get("addons", {})

        return {
            "project_name": "orchestrator",
            "project_config": {
                "project": {
                    "name": "orchestrator",
                    "ssl_email": project_config.get("ssl_email", ""),
                },
                "network": network_config,  # Add network config for subnet allocation
                "grafana": grafana_config,
                "prometheus": prometheus_config,
                "addons": addons_config,  # Include addons configuration
            },
            "addons": addons_config,  # Also pass at top-level for Ansible compatibility
            "enabled_addons": enabled_addons,
            "addon_configs": addon_configs,
        }


class OrchestratorLoader:
    """Loads orchestrator configuration"""

    def __init__(self, shared_dir: Path):
        """
        Initialize orchestrator loader

        Args:
            shared_dir: Path to shared directory
        """
        self.shared_dir = Path(shared_dir)
        self.orchestrator_dir = self.shared_dir / "orchestrator"
        self.config_path = self.orchestrator_dir / "config.yml"

    def load(self) -> OrchestratorConfig:
        """
        Load orchestrator configuration

        Returns:
            OrchestratorConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        return OrchestratorConfig(self.config_path)

    def exists(self) -> bool:
        """Check if orchestrator config exists"""
        return self.config_path.exists()
